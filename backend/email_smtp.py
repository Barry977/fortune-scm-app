"""邮件 SMTP 服务模块"""
import smtplib
import ssl
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List, Dict, Any

from backend.email_schemas import (
    SMTPConfigCreate, SMTPConfigUpdate, SMTPConfigResponse,
    EmailTemplateCreate, EmailTemplateUpdate,
    SendEmailRequest, SendEmailBatchRequest,
    TestSMTPRequest, TestSMTPResponse,
    EmailStats, EmailRecordResponse, EmailStatus
)

# 内存存储
_smtp_configs: Dict[str, dict] = {}
_templates: Dict[str, dict] = {}
_records: List[dict] = []
_stats = EmailStats()

def _id() -> str:
    return str(uuid.uuid4())[:8]

# ========== SMTP 配置 ==========

def create_smtp_config(data: SMTPConfigCreate, user_id: int) -> dict:
    cid = _id()
    config = {
        "id": cid, "name": data.name, "host": data.host, "port": data.port,
        "username": data.username, "password": data.password,
        "use_tls": data.use_tls, "use_ssl": data.use_ssl,
        "sender_name": data.sender_name, "sender_email": data.sender_email,
        "is_default": data.is_default if hasattr(data, 'is_default') else False,
        "created_by": user_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    if config["is_default"]:
        for c in _smtp_configs.values():
            c["is_default"] = False
    _smtp_configs[cid] = config
    return config

def get_smtp_config(config_id: str) -> Optional[dict]:
    return _smtp_configs.get(config_id)

def list_smtp_configs() -> List[dict]:
    return list(_smtp_configs.values())

def get_default_smtp_config() -> Optional[dict]:
    for c in _smtp_configs.values():
        if c.get("is_default"):
            return c
    return next(iter(_smtp_configs.values()), None)

def update_smtp_config(config_id: str, data: SMTPConfigUpdate) -> Optional[dict]:
    config = _smtp_configs.get(config_id)
    if not config:
        return None
    for k, v in data.dict(exclude_unset=True).items():
        config[k] = v
    config["updated_at"] = datetime.now().isoformat()
    return config

def delete_smtp_config(config_id: str) -> bool:
    return _smtp_configs.pop(config_id, None) is not None

# ========== SMTP 测试 ==========

def test_smtp_connection(request: TestSMTPRequest) -> TestSMTPResponse:
    """测试 SMTP 连接（用 config_id 或传入的配置）"""
    config = get_smtp_config(request.config_id) if request.config_id else get_default_smtp_config()
    if not config:
        return TestSMTPResponse(success=False, message="未找到SMTP配置")
    start = datetime.now()
    try:
        ctx = ssl.create_default_context()
        if config.get("use_ssl"):
            server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=10, context=ctx)
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=10)
            if config.get("use_tls"):
                server.starttls(context=ctx)
        server.login(config["username"], config["password"])
        # 发测试邮件
        msg = MIMEText(f"SMTP 连接测试成功 - {datetime.now()}", "plain", "utf-8")
        msg["Subject"] = "SMTP 连接测试"
        msg["From"] = config.get("sender_email") or config["username"]
        msg["To"] = request.test_email
        server.sendmail(msg["From"], [request.test_email], msg.as_string())
        server.quit()
        ms = int((datetime.now() - start).total_seconds() * 1000)
        return TestSMTPResponse(success=True, message=f"连接成功，测试邮件已发送至 {request.test_email}", latency_ms=ms)
    except Exception as e:
        ms = int((datetime.now() - start).total_seconds() * 1000)
        return TestSMTPResponse(success=False, message=f"连接失败: {e}", latency_ms=ms)

# ========== 邮件发送 ==========

def _connect(config: dict):
    ctx = ssl.create_default_context()
    if config.get("use_ssl"):
        server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=30, context=ctx)
    else:
        server = smtplib.SMTP(config["host"], config["port"], timeout=30)
        if config.get("use_tls"):
            server.starttls(context=ctx)
    server.login(config["username"], config["password"])
    return server

def _record(to_email: str, subject: str, status_val: str, config_id: str, user_id: int, error: str = ""):
    rec = {
        "id": _id(), "to_email": to_email, "subject": subject,
        "status": status_val, "smtp_config_id": config_id,
        "sent_by": user_id, "sent_at": datetime.now().isoformat(), "error": error
    }
    _records.insert(0, rec)
    _stats.total_sent += 1
    if status_val == EmailStatus.SENT.value:
        _stats.total_delivered += 1
    else:
        _stats.total_failed += 1
    return rec

def send_email(request: SendEmailRequest, user_id: int) -> dict:
    """发送邮件"""
    config = get_smtp_config(request.config_id) if request.config_id else get_default_smtp_config()
    if not config:
        raise ValueError("未找到SMTP配置")
    sender = config.get("sender_email") or config["username"]
    subject = request.subject or "(无主题)"
    body = request.body_text or ""
    html = request.body_html
    results = []
    try:
        server = _connect(config)
    except Exception as e:
        return {"success": False, "message": f"SMTP连接失败: {e}"}
    for recipient in request.to:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{config.get('sender_name', '')} <{sender}>" if config.get("sender_name") else sender
            msg["To"] = recipient.email
            msg["Subject"] = subject
            if request.cc:
                msg["Cc"] = ", ".join(request.cc)
            if body:
                msg.attach(MIMEText(body, "plain", "utf-8"))
            if html:
                msg.attach(MIMEText(html, "html", "utf-8"))
            all_rcpt = [recipient.email] + (request.cc or []) + (request.bcc or [])
            server.sendmail(sender, all_rcpt, msg.as_string())
            _record(recipient.email, subject, EmailStatus.SENT.value, config["id"], user_id)
            results.append({"email": recipient.email, "success": True})
        except Exception as e:
            _record(recipient.email, subject, EmailStatus.FAILED.value, config["id"], user_id, str(e))
            results.append({"email": recipient.email, "success": False, "error": str(e)})
    try:
        server.quit()
    except:
        pass
    ok = sum(1 for r in results if r["success"])
    return {"success": ok == len(results), "sent": ok, "failed": len(results) - ok, "results": results}

def send_batch_emails(request: SendEmailBatchRequest, user_id: int) -> dict:
    """批量发送（通过模板+收件人列表）"""
    config = get_smtp_config(request.config_id) if request.config_id else get_default_smtp_config()
    template = get_template(request.template_id) if request.template_id else None
    if not config:
        return {"success": False, "message": "未找到SMTP配置"}
    subject = template["subject"] if template else "(无主题)"
    body_text = template.get("body_text") or "" if template else ""
    body_html = template.get("body_html") or "" if template else ""
    sender = config.get("sender_email") or config["username"]
    results = []
    try:
        server = _connect(config)
    except Exception as e:
        return {"success": False, "message": f"SMTP连接失败: {e}"}
    for r in request.recipients:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = sender
            msg["To"] = r.email
            subj = subject
            for k, v in (r.variables or {}).items():
                subj = subj.replace(f"{{{k}}}", v)
            if r.name:
                subj = subj.replace("{name}", r.name)
            msg["Subject"] = subj
            body_t = body_text
            body_h = body_html
            for k, v in (r.variables or {}).items():
                body_t = body_t.replace(f"{{{k}}}", v)
                body_h = body_h.replace(f"{{{k}}}", v)
            if r.name:
                body_t = body_t.replace("{name}", r.name)
                body_h = body_h.replace("{name}", r.name)
            server.sendmail(sender, [r.email], msg.as_string())
            _record(r.email, subject, EmailStatus.SENT.value, config["id"], user_id)
            results.append({"email": r.email, "success": True})
        except Exception as e:
            _record(r.email, subject, EmailStatus.FAILED.value, config["id"], user_id, str(e))
            results.append({"email": r.email, "success": False, "error": str(e)})
    try:
        server.quit()
    except:
        pass
    ok = sum(1 for r in results if r["success"])
    return {"success": ok == len(results), "sent": ok, "failed": len(results) - ok, "results": results}

# ========== 模板管理 ==========

def create_template(data: EmailTemplateCreate, user_id: int) -> dict:
    tid = _id()
    t = {
        "id": tid, "name": data.name, "subject": data.subject,
        "body_html": data.body_html, "body_text": data.body_text,
        "category": data.category, "variables": data.variables or [],
        "is_active": data.is_active,
        "created_by": user_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    _templates[tid] = t
    return t

def get_template(template_id: str) -> Optional[dict]:
    return _templates.get(template_id)

def list_templates(category: Optional[str] = None) -> List[dict]:
    if category:
        return [t for t in _templates.values() if t.get("category") == category]
    return list(_templates.values())

def update_template(template_id: str, data: EmailTemplateUpdate) -> Optional[dict]:
    t = _templates.get(template_id)
    if not t:
        return None
    for k, v in data.dict(exclude_unset=True).items():
        t[k] = v
    t["updated_at"] = datetime.now().isoformat()
    return t

def delete_template(template_id: str) -> bool:
    return _templates.pop(template_id, None) is not None

# ========== 统计 ==========

def get_email_stats() -> EmailStats:
    today = datetime.now().strftime("%Y-%m-%d")
    _stats.today_sent = sum(1 for r in _records if r["sent_at"][:10] == today)
    _stats.today_delivered = sum(1 for r in _records if r["sent_at"][:10] == today and r["status"] == EmailStatus.SENT.value)
    return _stats

def get_email_records(limit: int = 50, status: Optional[str] = None) -> List[dict]:
    filtered = [r for r in _records if r["status"] == status] if status else _records
    return filtered[:limit]
