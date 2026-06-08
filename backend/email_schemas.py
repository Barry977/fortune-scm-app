from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class EmailStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SCHEDULED = "scheduled"

class SMTPConfigBase(BaseModel):
    """SMTP配置基础"""
    name: str = Field(..., min_length=1, max_length=50, description="配置名称")
    host: str = Field(..., min_length=1, max_length=100, description="SMTP服务器地址")
    port: int = Field(587, ge=1, le=65535, description="SMTP端口")
    username: str = Field(..., min_length=1, max_length=100, description="用户名/邮箱")
    password: str = Field(..., min_length=1, max_length=100, description="密码/授权码")
    use_tls: bool = Field(True, description="使用TLS")
    use_ssl: bool = Field(False, description="使用SSL")
    sender_name: Optional[str] = Field(None, max_length=100, description="发件人名称")
    sender_email: Optional[str] = Field(None, max_length=100, description="发件人邮箱")
    reply_to: Optional[str] = Field(None, max_length=100, description="回复邮箱")
    is_default: bool = Field(False, description="是否为默认配置")
    is_active: bool = Field(True, description="是否启用")

class SMTPConfigCreate(SMTPConfigBase):
    pass

class SMTPConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    host: Optional[str] = Field(None, min_length=1, max_length=100)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=1, max_length=100)
    use_tls: Optional[bool] = None
    use_ssl: Optional[bool] = None
    sender_name: Optional[str] = Field(None, max_length=100)
    sender_email: Optional[str] = Field(None, max_length=100)
    reply_to: Optional[str] = Field(None, max_length=100)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class SMTPConfigInDB(SMTPConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: int
    last_tested_at: Optional[datetime] = None
    last_test_result: Optional[bool] = None

class SMTPConfigResponse(SMTPConfigInDB):
    class Config:
        from_attributes = True

class EmailTemplateBase(BaseModel):
    """邮件模板基础"""
    name: str = Field(..., min_length=1, max_length=50, description="模板名称")
    subject: str = Field(..., min_length=1, max_length=200, description="邮件主题")
    body_html: Optional[str] = Field(None, description="HTML内容")
    body_text: Optional[str] = Field(None, description="纯文本内容")
    category: str = Field("general", max_length=50, description="分类")
    variables: Optional[List[str]] = Field(None, description="变量列表")
    is_active: bool = Field(True, description="是否启用")

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None

class EmailTemplateInDB(EmailTemplateBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: int
    usage_count: int = 0

class EmailTemplateResponse(EmailTemplateInDB):
    class Config:
        from_attributes = True

class EmailRecipient(BaseModel):
    """邮件收件人"""
    email: str
    name: Optional[str] = None
    variables: Optional[Dict[str, str]] = None

class SendEmailRequest(BaseModel):
    """发送邮件请求"""
    config_id: Optional[str] = Field(None, description="SMTP配置ID，不指定使用默认")
    template_id: Optional[str] = Field(None, description="模板ID，不指定使用自定义内容")
    to: List[EmailRecipient] = Field(..., description="收件人列表")
    cc: Optional[List[str]] = Field(None, description="抄送")
    bcc: Optional[List[str]] = Field(None, description="密送")
    subject: Optional[str] = Field(None, description="主题（不使用模板时）")
    body_html: Optional[str] = Field(None, description="HTML内容（不使用模板时）")
    body_text: Optional[str] = Field(None, description="文本内容（不使用模板时）")
    attachments: Optional[List[str]] = Field(None, description="附件路径列表")
    scheduled_at: Optional[datetime] = Field(None, description="定时发送时间")
    track_opens: bool = Field(True, description="追踪打开")
    track_clicks: bool = Field(True, description="追踪点击")

class SendEmailBatchRequest(BaseModel):
    """批量发送邮件请求"""
    config_id: Optional[str] = None
    template_id: str = Field(..., description="模板ID")
    recipients: List[EmailRecipient] = Field(..., description="收件人列表")
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None
    track_opens: bool = True
    track_clicks: bool = True
    batch_size: int = Field(50, ge=1, le=500, description="每批发送数量")
    delay_seconds: int = Field(1, ge=0, le=300, description="批次间隔秒数")

class EmailRecord(BaseModel):
    """邮件发送记录"""
    id: str
    config_id: str
    template_id: Optional[str] = None
    from_email: str
    to_email: str
    to_name: Optional[str] = None
    subject: str
    status: EmailStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    error_message: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

class EmailRecordResponse(EmailRecord):
    class Config:
        from_attributes = True

class EmailStats(BaseModel):
    """邮件统计"""
    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    total_failed: int = 0
    today_sent: int = 0
    today_delivered: int = 0
    today_opened: int = 0
    today_clicked: int = 0
    today_failed: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    delivery_rate: float = 0.0
    bounce_rate: float = 0.0

class TestSMTPRequest(BaseModel):
    """测试SMTP请求"""
    config_id: Optional[str] = None
    test_email: str = Field(..., description="测试收件邮箱")

class TestSMTPResponse(BaseModel):
    """测试SMTP响应"""
    success: bool
    message: str
    latency_ms: Optional[int] = None

# 预设邮件模板
DEFAULT_TEMPLATES = {
    "welcome": {
        "name": "欢迎邮件",
        "subject": "欢迎加入 FORTUNE SCM",
        "category": "onboarding",
        "body_html": """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">欢迎加入 FORTUNE SCM</h2>
                <p>尊敬的 {{name}}，</p>
                <p>感谢您选择 FORTUNE SCM 作为您的物流合作伙伴。</p>
                <p>我们专注于欧美中东空运 DDU 服务，为您提供：</p>
                <ul>
                    <li>全球空运网络覆盖</li>
                    <li>DDU 门到门服务</li>
                    <li>实时货物追踪</li>
                    <li>专业客服团队</li>
                </ul>
                <p>如有任何需求，请随时联系我们。</p>
                <p style="margin-top: 30px;">
                    <a href="{{login_url}}" style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">登录系统</a>
                </p>
                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    此邮件由 FORTUNE SCM 系统自动发送
                </p>
            </div>
        </body>
        </html>
        """,
        "body_text": """
        欢迎加入 FORTUNE SCM
        
        尊敬的 {{name}}，
        
        感谢您选择 FORTUNE SCM 作为您的物流合作伙伴。
        
        我们专注于欧美中东空运 DDU 服务。
        
        登录系统: {{login_url}}
        """,
        "variables": ["name", "login_url"]
    },
    "quote_followup": {
        "name": "报价跟进",
        "subject": "关于您的空运报价 - FORTUNE SCM",
        "category": "sales",
        "body_html": """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">报价跟进</h2>
                <p>尊敬的 {{name}}，</p>
                <p>感谢您对我们空运服务的关注。</p>
                <p>关于您查询的 {{route}} 航线：</p>
                <div style="background: #f3f4f6; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>航线：</strong>{{route}}</p>
                    <p><strong>预估价格：</strong>{{price}}</p>
                    <p><strong>时效：</strong>{{transit_time}}</p>
                </div>
                <p>如需确认订舱，请回复此邮件或致电我们。</p>
                <p>期待与您的合作！</p>
            </div>
        </body>
        </html>
        """,
        "body_text": """
        报价跟进
        
        尊敬的 {{name}}，
        
        关于您查询的 {{route}} 航线：
        
        预估价格: {{price}}
        时效: {{transit_time}}
        
        如需确认订舱，请回复此邮件。
        """,
        "variables": ["name", "route", "price", "transit_time"]
    },
    "shipment_update": {
        "name": "货物状态更新",
        "subject": "货物状态更新 - {{tracking_number}}",
        "category": "operations",
        "body_html": """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">货物状态更新</h2>
                <p>尊敬的 {{name}}，</p>
                <p>您的货物 {{tracking_number}} 状态已更新：</p>
                <div style="background: #f3f4f6; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><strong>当前状态：</strong>{{status}}</p>
                    <p><strong>位置：</strong>{{location}}</p>
                    <p><strong>更新时间：</strong>{{update_time}}</p>
                </div>
                <p>追踪链接: <a href="{{tracking_url}}">点击查看详情</a></p>
            </div>
        </body>
        </html>
        """,
        "body_text": """
        货物状态更新
        
        您的货物 {{tracking_number}} 状态已更新：
        
        当前状态: {{status}}
        位置: {{location}}
        更新时间: {{update_time}}
        
        追踪链接: {{tracking_url}}
        """,
        "variables": ["name", "tracking_number", "status", "location", "update_time", "tracking_url"]
    },
    "cold_outreach": {
        "name": "开发信",
        "subject": "{{company}} - 专业空运DDU服务合作机会",
        "category": "marketing",
        "body_html": """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <p>尊敬的 {{name}}，</p>
                <p>我是 FORTUNE SCM 的 {{sender_name}}，我们专注于欧美中东空运 DDU 服务。</p>
                <p>了解到 {{company}} 在 {{industry}} 领域的业务，相信我们的服务能为您的供应链带来价值：</p>
                <ul>
                    <li>覆盖欧美中东主要航线</li>
                    <li>DDU 门到门全程服务</li>
                    <li>竞争力的价格</li>
                    <li>24/7 客服支持</li>
                </ul>
                <p>不知道您近期是否有空运需求？我们可以为您提供免费报价。</p>
                <p>期待您的回复。</p>
                <p>Best regards,<br>{{sender_name}}<br>FORTUNE SCM</p>
            </div>
        </body>
        </html>
        """,
        "body_text": """
        尊敬的 {{name}}，
        
        我是 FORTUNE SCM 的 {{sender_name}}。
        
        我们专注于欧美中东空运 DDU 服务。
        
        了解到 {{company}} 的业务，相信我们的服务能为您带来价值。
        
        不知道您近期是否有空运需求？
        
        Best regards,
        {{sender_name}}
        FORTUNE SCM
        """,
        "variables": ["name", "company", "industry", "sender_name"]
    }
}
