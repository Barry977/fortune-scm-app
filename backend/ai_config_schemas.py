from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from enum import Enum


class AIModelProvider(str, Enum):
    """AI模型提供商（建议值，不限制用户输入）"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    TONGYI = "tongyi"
    WENXIN = "wenxin"
    KIMI = "kimi"
    MIMO = "mimo"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    QWEN = "qwen"
    SPARK = "spark"
    BAICHUAN = "baichuan"
    HUNYUAN = "hunyuan"
    DOUBAO = "doubao"
    STEP_FUN = "stepfun"
    MINIMAX = "minimax"

class AIModelType(str, Enum):
    """AI模型类型（建议值，不限制用户输入）"""
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4 = "gpt-4"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-20241022"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    QWEN_MAX = "qwen-max"
    QWEN_PLUS = "qwen-plus"
    QWEN_TURBO = "qwen-turbo"
    WENXIN_4 = "ernie-4.0"
    WENXIN_3_5 = "ernie-3.5"
    KIMI_MOONSHOT = "moonshot-v1-8k"
    KIMI_128K = "moonshot-v1-128k"
    MIMO_V2 = "mimo-v2"
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"
    GEMINI_PRO = "gemini-1.5-pro"
    GEMINI_FLASH = "gemini-1.5-flash"
    SPARK_MAX = "spark-max"
    BAICHUAN_4 = "baichuan-4"
    HUNYUAN_PRO = "hunyuan-pro"
    DOUBAO_PRO = "doubao-pro"
    STEP_2 = "step-2"
    MINIMAX_6_5 = "abab6.5"

# 模型与提供商映射（用于建议值，不用于验证）
MODEL_PROVIDER_MAP = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gpt-4": "openai",
    "claude-3-5-sonnet-20241022": "anthropic",
    "claude-3-5-haiku-20241022": "anthropic",
    "claude-3-opus-20240229": "anthropic",
    "qwen-max": "tongyi",
    "qwen-plus": "tongyi",
    "qwen-turbo": "tongyi",
    "ernie-4.0": "wenxin",
    "ernie-3.5": "wenxin",
    "moonshot-v1-8k": "kimi",
    "moonshot-v1-128k": "kimi",
    "mimo-v2": "mimo",
    "deepseek-chat": "deepseek",
    "deepseek-reasoner": "deepseek",
    "gemini-1.5-pro": "gemini",
    "gemini-1.5-flash": "gemini",
    "spark-max": "spark",
    "baichuan-4": "baichuan",
    "hunyuan-pro": "hunyuan",
    "doubao-pro": "doubao",
    "step-2": "stepfun",
    "abab6.5": "minimax",
}

# 模型显示名称
MODEL_DISPLAY_NAMES = {
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4": "GPT-4",
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
    "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
    "claude-3-opus-20240229": "Claude 3 Opus",
    "qwen-max": "通义千问 Max",
    "qwen-plus": "通义千问 Plus",
    "qwen-turbo": "通义千问 Turbo",
    "ernie-4.0": "文心一言 4.0",
    "ernie-3.5": "文心一言 3.5",
    "moonshot-v1-8k": "Kimi 8K",
    "moonshot-v1-128k": "Kimi 128K",
    "mimo-v2": "MiMo V2",
    "deepseek-chat": "DeepSeek Chat",
    "deepseek-reasoner": "DeepSeek Reasoner",
    "gemini-1.5-pro": "Gemini 1.5 Pro",
    "gemini-1.5-flash": "Gemini 1.5 Flash",
    "spark-max": "讯飞星火 Max",
    "baichuan-4": "百川智能 4.0",
    "hunyuan-pro": "腾讯混元 Pro",
    "doubao-pro": "豆包 Pro",
    "step-2": "阶跃星辰 Step-2",
    "abab6.5": "MiniMax abab6.5",
}

# 提供商显示名称
PROVIDER_DISPLAY_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "tongyi": "阿里云 (通义千问)",
    "wenxin": "百度 (文心一言)",
    "kimi": "月之暗面 (Kimi)",
    "mimo": "小米 (MiMo)",
    "deepseek": "DeepSeek",
    "gemini": "Google (Gemini)",
    "spark": "科大讯飞 (讯飞星火)",
    "baichuan": "百川智能",
    "hunyuan": "腾讯 (混元)",
    "doubao": "字节跳动 (豆包)",
    "stepfun": "阶跃星辰",
    "minimax": "MiniMax",
}

# 默认API基础URL
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "tongyi": "https://dashscope.aliyuncs.com/api/v1",
    "wenxin": "https://aip.baidubce.com/rpc/2.0",
    "kimi": "https://api.moonshot.cn/v1",
    "mimo": "https://api.mimo.ai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1",
    "spark": "https://spark-api-open.xf-yun.com/v1",
    "baichuan": "https://api.baichuan-ai.com/v1",
    "hunyuan": "https://hunyuan.tencentcloudapi.com",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "stepfun": "https://api.stepfun.com/v1",
    "minimax": "https://api.minimax.chat/v1",
}


class AIModelConfig(BaseModel):
    """AI模型配置"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=50, description="配置名称")
    provider: str = Field(..., description="模型提供商")
    model: str = Field(..., description="模型名称")
    api_key: str = Field(..., min_length=1, description="API密钥")
    base_url: Optional[str] = Field(None, description="自定义API基础URL")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, le=32000, description="最大token数")
    timeout: int = Field(30, ge=5, le=300, description="请求超时(秒)")
    is_default: bool = Field(False, description="是否为默认配置")
    is_active: bool = Field(True, description="是否启用")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class AIModelConfigCreate(BaseModel):
    """创建AI模型配置"""
    name: str = Field(..., min_length=1, max_length=50)
    provider: str = Field(..., description="模型提供商")
    model: str = Field(..., description="模型名称")
    api_key: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 30
    is_default: bool = False

class AIModelConfigUpdate(BaseModel):
    """更新AI模型配置"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    provider: Optional[str] = Field(None, description="模型提供商")
    model: Optional[str] = Field(None, description="模型名称")
    api_key: Optional[str] = Field(None, min_length=1)
    base_url: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    timeout: Optional[int] = Field(None, ge=5, le=300)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    provider: str = Field(..., description="模型提供商")
    model: str = Field(..., description="模型名称")
    api_key: str
    base_url: Optional[str] = None

class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool
    message: str
    latency_ms: Optional[int] = None
    model_info: Optional[Dict[str, Any]] = None

class AIGenerateRequest(BaseModel):
    """AI生成请求"""
    config_id: str = Field(..., description="AI配置ID")
    prompt: str = Field(..., min_length=1, max_length=10000, description="提示词")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    stream: bool = Field(False, description="是否流式输出")

class AIGenerateResponse(BaseModel):
    """AI生成响应"""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None

class MarketingContentRequest(BaseModel):
    """营销内容生成请求"""
    config_id: str
    content_type: str = Field(..., description="内容类型: email/social/post/ad")
    target_audience: str = Field(..., description="目标受众描述")
    product_service: str = Field(..., description="产品/服务描述")
    tone: str = Field("professional", description="语气: professional/friendly/urgent/casual")
    language: str = Field("zh", description="语言: zh/en")
    key_points: Optional[List[str]] = Field(None, description="关键要点")
    max_length: int = Field(500, ge=100, le=2000, description="最大长度")

class CustomerAnalysisRequest(BaseModel):
    """客户分析请求"""
    config_id: str
    customer_data: str = Field(..., description="客户数据(JSON或文本)")
    analysis_type: str = Field(..., description="分析类型: profile/needs/risk/opportunity")
    industry: Optional[str] = Field(None, description="行业")
    language: str = Field("zh", description="语言")

class AIUsageStats(BaseModel):
    """AI使用统计"""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    today_requests: int = 0
    today_tokens: int = 0
    today_cost: float = 0.0
    average_latency_ms: int = 0
    success_rate: float = 0.0
