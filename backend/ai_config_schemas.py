from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from enum import Enum

class AIModelProvider(str, Enum):
    """AI模型提供商"""
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
    """AI模型类型"""
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

# 模型与提供商映射
MODEL_PROVIDER_MAP = {
    AIModelType.GPT_4O: AIModelProvider.OPENAI,
    AIModelType.GPT_4O_MINI: AIModelProvider.OPENAI,
    AIModelType.GPT_4: AIModelProvider.OPENAI,
    AIModelType.CLAUDE_3_5_SONNET: AIModelProvider.ANTHROPIC,
    AIModelType.CLAUDE_3_5_HAIKU: AIModelProvider.ANTHROPIC,
    AIModelType.CLAUDE_3_OPUS: AIModelProvider.ANTHROPIC,
    AIModelType.QWEN_MAX: AIModelProvider.TONGYI,
    AIModelType.QWEN_PLUS: AIModelProvider.TONGYI,
    AIModelType.QWEN_TURBO: AIModelProvider.TONGYI,
    AIModelType.WENXIN_4: AIModelProvider.WENXIN,
    AIModelType.WENXIN_3_5: AIModelProvider.WENXIN,
    AIModelType.KIMI_MOONSHOT: AIModelProvider.KIMI,
    AIModelType.KIMI_128K: AIModelProvider.KIMI,
    AIModelType.MIMO_V2: AIModelProvider.MIMO,
    AIModelType.DEEPSEEK_CHAT: AIModelProvider.DEEPSEEK,
    AIModelType.DEEPSEEK_REASONER: AIModelProvider.DEEPSEEK,
    AIModelType.GEMINI_PRO: AIModelProvider.GEMINI,
    AIModelType.GEMINI_FLASH: AIModelProvider.GEMINI,
    AIModelType.SPARK_MAX: AIModelProvider.SPARK,
    AIModelType.BAICHUAN_4: AIModelProvider.BAICHUAN,
    AIModelType.HUNYUAN_PRO: AIModelProvider.HUNYUAN,
    AIModelType.DOUBAO_PRO: AIModelProvider.DOUBAO,
    AIModelType.STEP_2: AIModelProvider.STEP_FUN,
    AIModelType.MINIMAX_6_5: AIModelProvider.MINIMAX,
}

# 模型显示名称
MODEL_DISPLAY_NAMES = {
    AIModelType.GPT_4O: "GPT-4o",
    AIModelType.GPT_4O_MINI: "GPT-4o Mini",
    AIModelType.GPT_4: "GPT-4",
    AIModelType.CLAUDE_3_5_SONNET: "Claude 3.5 Sonnet",
    AIModelType.CLAUDE_3_5_HAIKU: "Claude 3.5 Haiku",
    AIModelType.CLAUDE_3_OPUS: "Claude 3 Opus",
    AIModelType.QWEN_MAX: "通义千问 Max",
    AIModelType.QWEN_PLUS: "通义千问 Plus",
    AIModelType.QWEN_TURBO: "通义千问 Turbo",
    AIModelType.WENXIN_4: "文心一言 4.0",
    AIModelType.WENXIN_3_5: "文心一言 3.5",
    AIModelType.KIMI_MOONSHOT: "Kimi 8K",
    AIModelType.KIMI_128K: "Kimi 128K",
    AIModelType.MIMO_V2: "MiMo V2",
    AIModelType.DEEPSEEK_CHAT: "DeepSeek Chat",
    AIModelType.DEEPSEEK_REASONER: "DeepSeek Reasoner",
    AIModelType.GEMINI_PRO: "Gemini 1.5 Pro",
    AIModelType.GEMINI_FLASH: "Gemini 1.5 Flash",
    AIModelType.SPARK_MAX: "讯飞星火 Max",
    AIModelType.BAICHUAN_4: "百川智能 4.0",
    AIModelType.HUNYUAN_PRO: "腾讯混元 Pro",
    AIModelType.DOUBAO_PRO: "豆包 Pro",
    AIModelType.STEP_2: "阶跃星辰 Step-2",
    AIModelType.MINIMAX_6_5: "MiniMax abab6.5",
}

# 提供商显示名称
PROVIDER_DISPLAY_NAMES = {
    AIModelProvider.OPENAI: "OpenAI",
    AIModelProvider.ANTHROPIC: "Anthropic",
    AIModelProvider.TONGYI: "阿里云 (通义千问)",
    AIModelProvider.WENXIN: "百度 (文心一言)",
    AIModelProvider.KIMI: "月之暗面 (Kimi)",
    AIModelProvider.MIMO: "小米 (MiMo)",
    AIModelProvider.DEEPSEEK: "DeepSeek",
    AIModelProvider.GEMINI: "Google (Gemini)",
    AIModelProvider.SPARK: "科大讯飞 (讯飞星火)",
    AIModelProvider.BAICHUAN: "百川智能",
    AIModelProvider.HUNYUAN: "腾讯 (混元)",
    AIModelProvider.DOUBAO: "字节跳动 (豆包)",
    AIModelProvider.STEP_FUN: "阶跃星辰",
    AIModelProvider.MINIMAX: "MiniMax",
}

# 默认API基础URL
DEFAULT_BASE_URLS = {
    AIModelProvider.OPENAI: "https://api.openai.com/v1",
    AIModelProvider.ANTHROPIC: "https://api.anthropic.com",
    AIModelProvider.TONGYI: "https://dashscope.aliyuncs.com/api/v1",
    AIModelProvider.WENXIN: "https://aip.baidubce.com/rpc/2.0",
    AIModelProvider.KIMI: "https://api.moonshot.cn/v1",
    AIModelProvider.MIMO: "https://api.mimo.ai/v1",
    AIModelProvider.DEEPSEEK: "https://api.deepseek.com/v1",
    AIModelProvider.GEMINI: "https://generativelanguage.googleapis.com/v1",
    AIModelProvider.SPARK: "https://spark-api-open.xf-yun.com/v1",
    AIModelProvider.BAICHUAN: "https://api.baichuan-ai.com/v1",
    AIModelProvider.HUNYUAN: "https://hunyuan.tencentcloudapi.com",
    AIModelProvider.DOUBAO: "https://ark.cn-beijing.volces.com/api/v3",
    AIModelProvider.STEP_FUN: "https://api.stepfun.com/v1",
    AIModelProvider.MINIMAX: "https://api.minimax.chat/v1",
}

class AIModelConfig(BaseModel):
    """AI模型配置"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=50, description="配置名称")
    provider: AIModelProvider
    model: AIModelType
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
    provider: AIModelProvider
    model: AIModelType
    api_key: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 30
    is_default: bool = False

class AIModelConfigUpdate(BaseModel):
    """更新AI模型配置"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    provider: Optional[AIModelProvider] = None
    model: Optional[AIModelType] = None
    api_key: Optional[str] = Field(None, min_length=1)
    base_url: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    timeout: Optional[int] = Field(None, ge=5, le=300)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    provider: AIModelProvider
    model: AIModelType
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
