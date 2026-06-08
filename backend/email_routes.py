from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from backend.auth import get_current_user, get_current_admin
from backend.email_smtp import (
    create_smtp_config, get_smtp_config, update_smtp_config,
    delete_smtp_config, list_smtp_configs, get_default_smtp_config,
    test_smtp_connection, send_email, send_batch_emails,
    create_template, get_template, update_template, delete_template,
    list_templates, get_email_stats, get_email_records
)
from backend.email_schemas import (
    SMTPConfigCreate, SMTPConfigUpdate, SMTPConfigResponse,
    EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse,
    SendEmailRequest, SendEmailBatchRequest,
    TestSMTPRequest, TestSMTPResponse,
    EmailStats, EmailRecordResponse
)

router = APIRouter(prefix="/api/email", tags=["邮件"])


@router.post("/smtp-configs", response_model=SMTPConfigResponse)
async def create_smtp(
    config_data: SMTPConfigCreate,
    current_user=Depends(get_current_user)
):
    """创建SMTP配置"""
    config = create_smtp_config(config_data, current_user.id)
    return SMTPConfigResponse(**config)


@router.get("/smtp-configs", response_model=List[SMTPConfigResponse])
async def list_smtp(
    current_user=Depends(get_current_user)
):
    """SMTP配置列表"""
    configs = list_smtp_configs()
    return [SMTPConfigResponse(**c) for c in configs]


@router.get("/smtp-configs/{config_id}", response_model=SMTPConfigResponse)
async def get_smtp(
    config_id: str,
    current_user=Depends(get_current_user)
):
    """获取SMTP配置"""
    config = get_smtp_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return SMTPConfigResponse(**config)


@router.put("/smtp-configs/{config_id}", response_model=SMTPConfigResponse)
async def update_smtp(
    config_id: str,
    config_data: SMTPConfigUpdate,
    current_user=Depends(get_current_user)
):
    """更新SMTP配置"""
    config = update_smtp_config(config_id, config_data)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return SMTPConfigResponse(**config)


@router.delete("/smtp-configs/{config_id}")
async def delete_smtp(
    config_id: str,
    current_user=Depends(get_current_user)
):
    """删除SMTP配置"""
    success = delete_smtp_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"message": "删除成功"}


@router.post("/test-smtp", response_model=TestSMTPResponse)
async def test_smtp(
    request: TestSMTPRequest,
    current_user=Depends(get_current_user)
):
    """测试SMTP连接"""
    try:
        result = test_smtp_connection(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send")
async def send_single_email(
    request: SendEmailRequest,
    current_user=Depends(get_current_user)
):
    """发送邮件"""
    try:
        result = send_email(request, current_user.id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-batch")
async def send_batch(
    request: SendEmailBatchRequest,
    current_user=Depends(get_current_user)
):
    """批量发送邮件"""
    try:
        result = send_batch_emails(request, current_user.id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates", response_model=EmailTemplateResponse)
async def create_email_template(
    template_data: EmailTemplateCreate,
    current_user=Depends(get_current_user)
):
    """创建邮件模板"""
    template = create_template(template_data, current_user.id)
    return EmailTemplateResponse(**template)


@router.get("/templates", response_model=List[EmailTemplateResponse])
async def list_email_templates(
    category: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """模板列表"""
    templates = list_templates(category)
    return [EmailTemplateResponse(**t) for t in templates]


@router.get("/templates/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: str,
    current_user=Depends(get_current_user)
):
    """获取模板"""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return EmailTemplateResponse(**template)


@router.put("/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: str,
    template_data: EmailTemplateUpdate,
    current_user=Depends(get_current_user)
):
    """更新模板"""
    template = update_template(template_id, template_data)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return EmailTemplateResponse(**template)


@router.delete("/templates/{template_id}")
async def delete_email_template(
    template_id: str,
    current_user=Depends(get_current_user)
):
    """删除模板"""
    success = delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"message": "删除成功"}


@router.get("/stats", response_model=EmailStats)
async def get_stats(
    current_user=Depends(get_current_user)
):
    """邮件统计"""
    return get_email_stats()


@router.get("/records")
async def get_records(
    limit: int = 50,
    status: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """发送记录"""
    records = get_email_records(limit, status)
    return {
        "records": [EmailRecordResponse(**r).dict() for r in records],
        "total": len(records)
    }
