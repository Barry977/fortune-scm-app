"""邮件 SMTP 服务模块 — SQLite-backed"""
import smtplib
import ssl
import json
import uuid
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Optional, List, Dict, Any

from backend.database import get_db_ctx
from backend.email_schemas import (
    SMTPConfigCreate, SMTPConfigUpdate, SMTPConfigResponse, SMTPConfigInDB,
    EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse, EmailTemplateInDB,
    SendEmailRequest, SendEmailBatchRequest,
    TestSMTPRequest, TestSMTPResponse,
    EmailStats, EmailRecordResponse, EmailRecord, EmailStatus,
    EmailRecipient, DEFAULT_TEMPLATES,
)

# ---------------------------------------------------------------------------
# ID helper
# ---------------------------------------------------------------------------

def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Table initialisation (called from database.init_db or independently)
# ---------------------------------------------------------------------------

def init_email_tables():
    """Create email-related tables if they don't exist.
    Drops legacy tables (email_configs, email_templates, email_records) that
    had a different schema so the new ones can be created cleanly."""
    with get_db_ctx() as conn:
        # Drop legacy tables that had incompatible schemas
        conn.execute("DROP TABLE IF EXISTS email_configs")
        conn.execute("DROP TABLE IF EXISTS email_records")
        conn.execute("DROP TABLE IF EXISTS email_templates")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS email_smtp_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL DEFAULT 587,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                use_tls INTEGER NOT NULL DEFAULT 1,
                use_ssl INTEGER NOT NULL DEFAULT 0,
                sender_name TEXT,
                sender_email TEXT,
                reply_to TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER NOT NULL DEFAULT 0,
                last_tested_at TEXT,
                last_test_result INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_html TEXT,
                body_text TEXT,
                category TEXT NOT NULL DEFAULT 'general',
                variables TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER NOT NULL DEFAULT 0,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_send_records (
                id TEXT PRIMARY KEY,
                config_id TEXT,
                template_id TEXT,
                from_email TEXT NOT NULL,
                to_email TEXT NOT NULL,
                to_name TEXT,
                subject TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                sent_at TEXT,
                delivered_at TEXT,
                opened_at TEXT,
                clicked_at TEXT,
                error_message TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_by INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """)


# =====================================================================
#  SMTP Config CRUD
# =====================================================================

def _row_to_dict(row) -> dict:
    """Convert sqlite3.Row to plain dict."""
    return dict(row)


def _config_row_to_response(row: dict) -> dict:
    """Normalise a DB row into a dict suitable for SMTPConfigResponse."""
    return {
        "id": row["id"],
        "name": row["name"],
        "host": row["host"],
        "port": row["port"],
        "username": row["username"],
        "password": row["password"],
        "use_tls": bool(row["use_tls"]),
        "use_ssl": bool(row["use_ssl"]),
        "sender_name": row.get("sender_name"),
        "sender_email": row.get("sender_email"),
        "reply_to": row.get("reply_to"),
        "is_default": bool(row["is_default"]),
        "is_active": bool(row["is_active"]),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_tested_at": row.get("last_tested_at"),
        "last_test_result": bool(row["last_test_result"]) if row.get("last_test_result") is not None else None,
    }


def create_smtp_config(data: SMTPConfigCreate, user_id: int) -> dict:
    cid = _uid()
    now = datetime.utcnow().isoformat()
    # If this config is set as default, unset all others first
    with get_db_ctx() as conn:
        if data.is_default:
            conn.execute("UPDATE email_smtp_configs SET is_default = 0")
        conn.execute(
            """INSERT INTO email_smtp_configs
               (id, name, host, port, username, password, use_tls, use_ssl,
                sender_name, sender_email, reply_to, is_default, is_active,
                created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, data.name, data.host, data.port, data.username, data.password,
             int(data.use_tls), int(data.use_ssl),
             data.sender_name, data.sender_email, data.reply_to,
             int(data.is_default), int(data.is_active),
             user_id, now, now),
        )
    return get_smtp_config(cid)


def get_smtp_config(config_id: str) -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM email_smtp_configs WHERE id = ?", (config_id,)).fetchone()
    return _config_row_to_response(_row_to_dict(row)) if row else None


def list_smtp_configs() -> List[dict]:
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM email_smtp_configs ORDER BY is_default DESC, created_at DESC").fetchall()
    return [_config_row_to_response(_row_to_dict(r)) for r in rows]


def get_default_smtp_config() -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM email_smtp_configs WHERE is_default = 1 AND is_active = 1").fetchone()
        if not row:
            row = conn.execute("SELECT * FROM email_smtp_configs WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1").fetchone()
    if row:
        return _config_row_to_response(_row_to_dict(row))
    return None


def update_smtp_config(config_id: str, data: SMTPConfigUpdate) -> Optional[dict]:
    existing = get_smtp_config(config_id)
    if not existing:
        return None
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return existing
    # Convert booleans to int for SQLite
    for k in ("use_tls", "use_ssl", "is_default", "is_active"):
        if k in updates:
            updates[k] = int(updates[k])
    # Handle default flag
    now = datetime.utcnow().isoformat()
    with get_db_ctx() as conn:
        if updates.get("is_default"):
            conn.execute("UPDATE email_smtp_configs SET is_default = 0")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [now, config_id]
        conn.execute(f"UPDATE email_smtp_configs SET {set_clause}, updated_at = ? WHERE id = ?", vals)
    return get_smtp_config(config_id)


def delete_smtp_config(config_id: str) -> bool:
    with get_db_ctx() as conn:
        cur = conn.execute("DELETE FROM email_smtp_configs WHERE id = ?", (config_id,))
    return cur.rowcount > 0


# =====================================================================
#  SMTP Test Connection
# =====================================================================

def test_smtp_connection(request: TestSMTPRequest) -> TestSMTPResponse:
    config = get_smtp_config(request.config_id) if request.config_id else get_default_smtp_config()
    if not config:
        return TestSMTPResponse(success=False, message="未找到SMTP配置")
    start = time.time()
    try:
        ctx = ssl.create_default_context()
        if config.get("use_ssl"):
            server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=15, context=ctx)
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=15)
            if config.get("use_tls"):
                server.starttls(context=ctx)
        server.login(config["username"], config["password"])
        # Send test email
        msg = MIMEText(f"SMTP 连接测试成功 — {datetime.utcnow().isoformat()}", "plain", "utf-8")
        msg["Subject"] = "SMTP 连接测试"
        sender = config.get("sender_email") or config["username"]
        msg["From"] = config.get("sender_name", sender)
        msg["To"] = request.test_email
        server.sendmail(sender, [request.test_email], msg.as_string())
        server.quit()
        ms = int((time.time() - start) * 1000)
        # Update last-tested info
        _update_test_result(config["id"], True)
        return TestSMTPResponse(success=True, message=f"连接成功，测试邮件已发送至 {request.test_email}", latency_ms=ms)
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        _update_test_result(config["id"], False)
        return TestSMTPResponse(success=False, message=f"连接失败: {e}", latency_ms=ms)


def _update_test_result(config_id: str, result: bool):
    now = datetime.utcnow().isoformat()
    with get_db_ctx() as conn:
        conn.execute(
            "UPDATE email_smtp_configs SET last_tested_at = ?, last_test_result = ?, updated_at = ? WHERE id = ?",
            (now, int(result), now, config_id),
        )


# =====================================================================
#  Email Sending
# =====================================================================

def _connect(config: dict):
    """Create an authenticated SMTP connection."""
    ctx = ssl.create_default_context()
    if config.get("use_ssl"):
        server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=30, context=ctx)
    else:
        server = smtplib.SMTP(config["host"], config["port"], timeout=30)
        if config.get("use_tls"):
            server.starttls(context=ctx)
    server.login(config["username"], config["password"])
    return server


def _build_sender_field(config: dict) -> str:
    sender = config.get("sender_email") or config["username"]
    name = config.get("sender_name")
    if name:
        return f"{name} <{sender}>"
    return sender


def _build_message(
    sender_field: str,
    to_email: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    cc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_field
    msg["To"] = to_email
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to:
        msg["Reply-To"] = reply_to
    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    return msg


def _render_template_vars(text: str, variables: Dict[str, str]) -> str:
    """Replace {{var}} placeholders."""
    for k, v in (variables or {}).items():
        text = text.replace(f"{{{{{k}}}}}", v)
    return text


def _save_record(
    config_id: str,
    template_id: Optional[str],
    from_email: str,
    to_email: str,
    to_name: Optional[str],
    subject: str,
    status_val: str,
    created_by: int,
    error: str = "",
):
    now = datetime.utcnow().isoformat()
    rid = _uid()
    with get_db_ctx() as conn:
        conn.execute(
            """INSERT INTO email_send_records
               (id, config_id, template_id, from_email, to_email, to_name,
                subject, status, sent_at, error_message, created_by, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, config_id, template_id, from_email, to_email, to_name,
             subject, status_val,
             now if status_val == EmailStatus.SENT.value else None,
             error or None, created_by, now),
        )
    return rid


def _increment_template_usage(template_id: str):
    with get_db_ctx() as conn:
        conn.execute("UPDATE email_templates SET usage_count = usage_count + 1 WHERE id = ?", (template_id,))


def send_email(request: SendEmailRequest, user_id: int) -> dict:
    """Send one-off email to one or more recipients."""
    config = get_smtp_config(request.config_id) if request.config_id else get_default_smtp_config()
    if not config:
        raise ValueError("未找到SMTP配置")

    template = None
    template_id = request.template_id
    if template_id:
        template = get_template(template_id)

    subject = request.subject or (template["subject"] if template else "(无主题)")
    body_html = request.body_html or (template.get("body_html") if template else None)
    body_text = request.body_text or (template.get("body_text") if template else None)
    sender = config.get("sender_email") or config["username"]
    sender_field = _build_sender_field(config)

    # Connect
    try:
        server = _connect(config)
    except Exception as e:
        raise ValueError(f"SMTP连接失败: {e}")

    results = []
    for recipient in request.to:
        # Merge per-recipient variables into template
        vars_ = dict(recipient.variables or {})
        if recipient.name:
            vars_["name"] = recipient.name
        subj = _render_template_vars(subject, vars_)
        h = _render_template_vars(body_html, vars_) if body_html else None
        t = _render_template_vars(body_text, vars_) if body_text else None

        try:
            msg = _build_message(sender_field, recipient.email, subj, h, t, request.cc, config.get("reply_to"))
            all_rcpt = [recipient.email] + (request.cc or []) + (request.bcc or [])
            server.sendmail(sender, all_rcpt, msg.as_string())
            _save_record(config.get("id"), template_id, sender, recipient.email, recipient.name, subj, EmailStatus.SENT.value, user_id)
            results.append({"email": recipient.email, "success": True})
        except Exception as e:
            _save_record(config.get("id"), template_id, sender, recipient.email, recipient.name, subj, EmailStatus.FAILED.value, user_id, str(e))
            results.append({"email": recipient.email, "success": False, "error": str(e)})

    try:
        server.quit()
    except Exception:
        pass

    if template_id:
        _increment_template_usage(template_id)

    ok = sum(1 for r in results if r["success"])
    return {"success": ok == len(results), "sent": ok, "failed": len(results) - ok, "results": results}


def send_batch_emails(request: SendEmailBatchRequest, user_id: int) -> dict:
    """Batch-send emails using a template + recipient list, with batching and delay."""
    config = get_smtp_config(request.config_id) if request.config_id else get_default_smtp_config()
    if not config:
        raise ValueError("未找到SMTP配置")
    template = get_template(request.template_id) if request.template_id else None
    if not template:
        raise ValueError("未找到邮件模板")

    subject_tpl = template["subject"]
    body_text_tpl = template.get("body_text") or ""
    body_html_tpl = template.get("body_html") or ""
    sender = config.get("sender_email") or config["username"]
    sender_field = _build_sender_field(config)
    reply_to = config.get("reply_to")

    all_results = []
    batch_size = request.batch_size
    delay = request.delay_seconds

    for batch_start in range(0, len(request.recipients), batch_size):
        batch = request.recipients[batch_start:batch_start + batch_size]
        # Re-connect per batch to avoid stale connections
        try:
            server = _connect(config)
        except Exception as e:
            for r in batch:
                _save_record(config["id"], request.template_id, sender, r.email, r.name, subject_tpl, EmailStatus.FAILED.value, user_id, str(e))
                all_results.append({"email": r.email, "success": False, "error": str(e)})
            continue

        for r in batch:
            vars_ = dict(r.variables or {})
            if r.name:
                vars_["name"] = r.name
            subj = _render_template_vars(subject_tpl, vars_)
            h = _render_template_vars(body_html_tpl, vars_)
            t = _render_template_vars(body_text_tpl, vars_)
            try:
                msg = _build_message(sender_field, r.email, subj, h, t, request.cc, reply_to)
                all_rcpt = [r.email] + (request.cc or []) + (request.bcc or [])
                server.sendmail(sender, all_rcpt, msg.as_string())
                _save_record(config["id"], request.template_id, sender, r.email, r.name, subj, EmailStatus.SENT.value, user_id)
                all_results.append({"email": r.email, "success": True})
            except Exception as e:
                _save_record(config["id"], request.template_id, sender, r.email, r.name, subj, EmailStatus.FAILED.value, user_id, str(e))
                all_results.append({"email": r.email, "success": False, "error": str(e)})

        try:
            server.quit()
        except Exception:
            pass

        # Delay between batches (not after last batch)
        if batch_start + batch_size < len(request.recipients) and delay > 0:
            time.sleep(delay)

    _increment_template_usage(request.template_id)
    ok = sum(1 for r in all_results if r["success"])
    return {"success": ok == len(all_results), "sent": ok, "failed": len(all_results) - ok, "results": all_results}


# =====================================================================
#  Email Template CRUD
# =====================================================================

def _template_row_to_response(row: dict) -> dict:
    variables = row.get("variables")
    if isinstance(variables, str):
        try:
            variables = json.loads(variables)
        except (json.JSONDecodeError, TypeError):
            variables = []
    return {
        "id": row["id"],
        "name": row["name"],
        "subject": row["subject"],
        "body_html": row.get("body_html"),
        "body_text": row.get("body_text"),
        "category": row.get("category", "general"),
        "variables": variables or [],
        "is_active": bool(row.get("is_active", 1)),
        "created_by": row["created_by"],
        "usage_count": row.get("usage_count", 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_template(data: EmailTemplateCreate, user_id: int) -> dict:
    tid = _uid()
    now = datetime.utcnow().isoformat()
    with get_db_ctx() as conn:
        conn.execute(
            """INSERT INTO email_templates
               (id, name, subject, body_html, body_text, category, variables,
                is_active, created_by, usage_count, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tid, data.name, data.subject, data.body_html, data.body_text,
             data.category, json.dumps(data.variables or []),
             int(data.is_active), user_id, 0, now, now),
        )
    return get_template(tid)


def get_template(template_id: str) -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM email_templates WHERE id = ?", (template_id,)).fetchone()
    return _template_row_to_response(_row_to_dict(row)) if row else None


def list_templates(category: Optional[str] = None) -> List[dict]:
    with get_db_ctx() as conn:
        if category:
            rows = conn.execute("SELECT * FROM email_templates WHERE category = ? ORDER BY created_at DESC", (category,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM email_templates ORDER BY created_at DESC").fetchall()
    return [_template_row_to_response(_row_to_dict(r)) for r in rows]


def update_template(template_id: str, data: EmailTemplateUpdate) -> Optional[dict]:
    existing = get_template(template_id)
    if not existing:
        return None
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return existing
    if "variables" in updates:
        updates["variables"] = json.dumps(updates["variables"] or [])
    if "is_active" in updates:
        updates["is_active"] = int(updates["is_active"])
    now = datetime.utcnow().isoformat()
    with get_db_ctx() as conn:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [now, template_id]
        conn.execute(f"UPDATE email_templates SET {set_clause}, updated_at = ? WHERE id = ?", vals)
    return get_template(template_id)


def delete_template(template_id: str) -> bool:
    with get_db_ctx() as conn:
        cur = conn.execute("DELETE FROM email_templates WHERE id = ?", (template_id,))
    return cur.rowcount > 0


def seed_default_templates(user_id: int = 0):
    """Insert built-in templates if they don't already exist."""
    with get_db_ctx() as conn:
        existing = conn.execute("SELECT COUNT(*) as c FROM email_templates").fetchone()["c"]
    if existing > 0:
        return
    for key, tpl in DEFAULT_TEMPLATES.items():
        create_template(
            EmailTemplateCreate(
                name=tpl["name"],
                subject=tpl["subject"],
                body_html=tpl.get("body_html"),
                body_text=tpl.get("body_text"),
                category=tpl.get("category", "general"),
                variables=tpl.get("variables", []),
            ),
            user_id,
        )


# =====================================================================
#  Send Records & Stats
# =====================================================================

def _record_row_to_response(row: dict) -> dict:
    return {
        "id": row["id"],
        "config_id": row.get("config_id", ""),
        "template_id": row.get("template_id"),
        "from_email": row["from_email"],
        "to_email": row["to_email"],
        "to_name": row.get("to_name"),
        "subject": row["subject"],
        "status": row["status"],
        "sent_at": row.get("sent_at"),
        "delivered_at": row.get("delivered_at"),
        "opened_at": row.get("opened_at"),
        "clicked_at": row.get("clicked_at"),
        "error_message": row.get("error_message"),
        "ip_address": row.get("ip_address"),
        "user_agent": row.get("user_agent"),
        "created_at": row["created_at"],
    }


def get_email_records(limit: int = 50, status: Optional[str] = None) -> List[dict]:
    with get_db_ctx() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM email_send_records WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM email_send_records ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_record_row_to_response(_row_to_dict(r)) for r in rows]


def get_email_stats() -> EmailStats:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_db_ctx() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM email_send_records").fetchone()["c"]
        sent = conn.execute("SELECT COUNT(*) as c FROM email_send_records WHERE status = 'sent'").fetchone()["c"]
        failed = conn.execute("SELECT COUNT(*) as c FROM email_send_records WHERE status = 'failed'").fetchone()["c"]
        today_sent = conn.execute(
            "SELECT COUNT(*) as c FROM email_send_records WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()["c"]
        today_failed = conn.execute(
            "SELECT COUNT(*) as c FROM email_send_records WHERE created_at LIKE ? AND status = 'failed'", (f"{today}%",)
        ).fetchone()["c"]
        today_ok = conn.execute(
            "SELECT COUNT(*) as c FROM email_send_records WHERE created_at LIKE ? AND status = 'sent'", (f"{today}%",)
        ).fetchone()["c"]

    delivery_rate = (sent / total * 100) if total else 0.0
    bounce_rate = (failed / total * 100) if total else 0.0
    return EmailStats(
        total_sent=total,
        total_delivered=sent,
        total_failed=failed,
        today_sent=today_sent,
        today_delivered=today_ok,
        today_failed=today_failed,
        delivery_rate=round(delivery_rate, 2),
        bounce_rate=round(bounce_rate, 2),
    )


# =====================================================================
#  Import legacy JSON config (one-time migration helper)
# =====================================================================

def import_legacy_smtp_json(json_path: str, user_id: int = 0):
    """Import ~/.openclaw/agents/sales/data/smtp_config.json into DB (skip if already exists)."""
    import os
    if not os.path.exists(json_path):
        return
    with open(json_path, "r") as f:
        cfg = json.load(f)
    # Check if already imported (by host+username match)
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT id FROM email_smtp_configs WHERE host = ? AND username = ?",
            (cfg.get("smtp_server", ""), cfg.get("username", "")),
        ).fetchone()
    if row:
        return
    create_smtp_config(
        SMTPConfigCreate(
            name="Legacy Import",
            host=cfg.get("smtp_server", ""),
            port=cfg.get("smtp_port", 465),
            username=cfg.get("username", ""),
            password=cfg.get("password", ""),
            use_tls=not cfg.get("use_ssl", False),
            use_ssl=cfg.get("use_ssl", False),
            sender_name=cfg.get("from_name"),
            sender_email=cfg.get("from_email"),
            is_default=True,
        ),
        user_id,
    )
