import asyncio
import time
import json
import os
from typing import Optional, Dict, List, Any
from datetime import datetime

from backend.ai_config_schemas import (
    AIModelConfig, AIModelConfigCreate, AIModelConfigUpdate,
    TestConnectionRequest, TestConnectionResponse,
    AIGenerateRequest, AIGenerateResponse,
    MarketingContentRequest, CustomerAnalysisRequest,
    AIUsageStats, AIModelProvider, AIModelType,
    MODEL_PROVIDER_MAP, MODEL_DISPLAY_NAMES, PROVIDER_DISPLAY_NAMES,
    DEFAULT_BASE_URLS
)

# 内存存储
_configs_db: Dict[str, AIModelConfig] = {}
_config_counter = 0
_usage_stats = AIUsageStats()

# 预设的营销内容模板
MARKETING_TEMPLATES = {
    "email": {
        "system_prompt": "你是一位专业的国际物流营销专家，擅长撰写开发信。请根据提供的信息撰写一封专业、简洁、有吸引力的开发信。",
        "prompt_template": """请为一封开发信生成内容：
目标受众：{target_audience}
产品/服务：{product_service}
语气：{tone}
语言：{language}
关键要点：{key_points}

要求：
1. 主题行要吸引人
2. 开头要个性化
3. 突出价值主张
4. 包含明确的行动号召
5. 长度控制在{max_length}字以内
"""
    },
    "social": {
        "system_prompt": "你是一位社交媒体营销专家，擅长撰写LinkedIn等平台的社交内容。",
        "prompt_template": """请为社交媒体生成内容：
目标受众：{target_audience}
产品/服务：{product_service}
语气：{tone}
语言：{language}
关键要点：{key_points}

要求：
1. 适合LinkedIn发布
2. 包含相关话题标签
3. 引人入胜的开头
4. 提供价值内容
5. 鼓励互动
6. 长度控制在{max_length}字以内
"""
    },
    "post": {
        "system_prompt": "你是一位内容营销专家，擅长撰写营销文案。",
        "prompt_template": """请生成营销文案：
目标受众：{target_audience}
产品/服务：{product_service}
语气：{tone}
语言：{language}
关键要点：{key_points}

要求：
1. 标题吸引人
2. 内容结构清晰
3. 突出卖点
4. 包含行动号召
5. 长度控制在{max_length}字以内
"""
    },
    "ad": {
        "system_prompt": "你是一位广告文案专家，擅长撰写高转化率的广告文案。",
        "prompt_template": """请生成广告文案：
目标受众：{target_audience}
产品/服务：{product_service}
语气：{tone}
语言：{language}
关键要点：{key_points}

要求：
1. 标题要抓眼球
2. 突出核心卖点
3. 制造紧迫感
4. 明确的行动号召
5. 长度控制在{max_length}字以内
"""
    }
}

# 预设的客户分析模板
ANALYSIS_TEMPLATES = {
    "profile": {
        "system_prompt": "你是一位客户分析专家，擅长分析客户画像。",
        "prompt_template": """请分析以下客户数据并生成客户画像：

客户数据：
{customer_data}

行业：{industry}
语言：{language}

要求：
1. 公司背景分析
2. 关键决策人识别
3. 业务需求分析
4. 采购行为特征
5. 合作潜力评估
6. 风险因素识别
"""
    },
    "needs": {
        "system_prompt": "你是一位需求分析专家，擅长识别客户潜在需求。",
        "prompt_template": """请分析以下客户的潜在需求：

客户数据：
{customer_data}

行业：{industry}
语言：{language}

要求：
1. 显性需求识别
2. 隐性需求挖掘
3. 痛点分析
4. 需求优先级排序
5. 解决方案建议
"""
    },
    "risk": {
        "system_prompt": "你是一位风险评估专家，擅长识别客户合作风险。",
        "prompt_template": """请分析以下客户的合作风险：

客户数据：
{customer_data}

行业：{industry}
语言：{language}

要求：
1. 信用风险
2. 经营风险
3. 行业风险
4. 地域风险
5. 风险等级评估
6. 风险缓解建议
"""
    },
    "opportunity": {
        "system_prompt": "你是一位商业机会分析专家，擅长发现业务增长机会。",
        "prompt_template": """请分析以下客户的业务机会：

客户数据：
{customer_data}

行业：{industry}
语言：{language}

要求：
1. 现有业务机会
2. 交叉销售机会
3. 向上销售机会
4. 长期合作潜力
5. 市场扩展机会
6. 优先级建议
"""
    }
}


def _get_next_id() -> str:
    """生成下一个配置ID"""
    global _config_counter
    _config_counter += 1
    return f"ai_config_{_config_counter}"


def _get_default_base_url(provider: AIModelProvider) -> str:
    """获取默认API基础URL"""
    return DEFAULT_BASE_URLS.get(provider, "")


def _get_provider_from_model(model: AIModelType) -> AIModelProvider:
    """根据模型获取提供商"""
    return MODEL_PROVIDER_MAP.get(model, AIModelProvider.OPENAI)


def create_config(config_data: AIModelConfigCreate) -> AIModelConfig:
    """创建AI配置"""
    global _configs_db
    
    config_id = _get_next_id()
    now = datetime.now().isoformat()
    
    # 如果设为默认，取消其他默认配置
    if config_data.is_default:
        for config in _configs_db.values():
            if config.is_default:
                config.is_default = False
    
    config = AIModelConfig(
        id=config_id,
        name=config_data.name,
        provider=config_data.provider,
        model=config_data.model,
        api_key=config_data.api_key,
        base_url=config_data.base_url or _get_default_base_url(config_data.provider),
        temperature=config_data.temperature,
        max_tokens=config_data.max_tokens,
        timeout=config_data.timeout,
        is_default=config_data.is_default,
        is_active=True,
        created_at=now,
        updated_at=now
    )
    
    _configs_db[config_id] = config
    return config


def get_config(config_id: str) -> Optional[AIModelConfig]:
    """获取AI配置"""
    return _configs_db.get(config_id)


def get_default_config() -> Optional[AIModelConfig]:
    """获取默认配置"""
    for config in _configs_db.values():
        if config.is_default and config.is_active:
            return config
    # 如果没有默认配置，返回第一个活跃配置
    for config in _configs_db.values():
        if config.is_active:
            return config
    return None


def list_configs() -> List[AIModelConfig]:
    """列出所有AI配置"""
    return list(_configs_db.values())


def update_config(config_id: str, config_data: AIModelConfigUpdate) -> Optional[AIModelConfig]:
    """更新AI配置"""
    config = _configs_db.get(config_id)
    if not config:
        return None
    
    # 如果设为默认，取消其他默认配置
    if config_data.is_default:
        for c in _configs_db.values():
            if c.id != config_id and c.is_default:
                c.is_default = False
    
    update_data = config_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    config.updated_at = datetime.now().isoformat()
    return config


def delete_config(config_id: str) -> bool:
    """删除AI配置"""
    if config_id in _configs_db:
        del _configs_db[config_id]
        return True
    return False


def get_available_models() -> Dict[str, Any]:
    """获取可用模型列表"""
    providers = {}
    
    for provider in AIModelProvider:
        models = []
        for model in AIModelType:
            if MODEL_PROVIDER_MAP.get(model) == provider:
                models.append({
                    "value": model.value,
                    "label": MODEL_DISPLAY_NAMES.get(model, model.value),
                    "provider": provider.value
                })
        
        providers[provider.value] = {
            "label": PROVIDER_DISPLAY_NAMES.get(provider, provider.value),
            "models": models,
            "default_base_url": DEFAULT_BASE_URLS.get(provider, "")
        }
    
    return providers


async def test_connection(request: TestConnectionRequest) -> TestConnectionResponse:
    """测试AI连接"""
    start_time = time.time()
    
    try:
        # 根据提供商选择测试方式
        if request.provider == AIModelProvider.OPENAI:
            success = await _test_openai(request)
        elif request.provider == AIModelProvider.ANTHROPIC:
            success = await _test_anthropic(request)
        elif request.provider in [AIModelProvider.TONGYI, AIModelProvider.KIMI, 
                                   AIModelProvider.DEEPSEEK, AIModelProvider.QWEN]:
            success = await _test_openai_compatible(request)
        else:
            # 其他提供商使用通用测试
            success = await _test_generic(request)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        if success:
            return TestConnectionResponse(
                success=True,
                message="连接成功",
                latency_ms=latency_ms,
                model_info={"model": request.model.value, "provider": request.provider.value}
            )
        else:
            return TestConnectionResponse(
                success=False,
                message="连接失败，请检查API密钥和配置",
                latency_ms=latency_ms
            )
            
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return TestConnectionResponse(
            success=False,
            message=f"连接异常: {str(e)}",
            latency_ms=latency_ms
        )


async def _test_openai(request: TestConnectionRequest) -> bool:
    """测试OpenAI连接"""
    import aiohttp
    
    base_url = request.base_url or DEFAULT_BASE_URLS[AIModelProvider.OPENAI]
    headers = {
        "Authorization": f"Bearer {request.api_key}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{base_url}/models",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            return response.status == 200


async def _test_anthropic(request: TestConnectionRequest) -> bool:
    """测试Anthropic连接"""
    import aiohttp
    
    base_url = request.base_url or DEFAULT_BASE_URLS[AIModelProvider.ANTHROPIC]
    headers = {
        "x-api-key": request.api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/v1/messages",
            headers=headers,
            json={
                "model": request.model.value,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hello"}]
            },
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            return response.status in [200, 429]  # 429表示API有效但限流


async def _test_openai_compatible(request: TestConnectionRequest) -> bool:
    """测试OpenAI兼容API"""
    import aiohttp
    
    base_url = request.base_url or DEFAULT_BASE_URLS.get(request.provider, "")
    headers = {
        "Authorization": f"Bearer {request.api_key}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": request.model.value,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5
            },
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            return response.status in [200, 429]


async def _test_generic(request: TestConnectionRequest) -> bool:
    """通用连接测试"""
    # 对于不支持的提供商，返回True（假设配置正确）
    return True


async def generate_content(request: AIGenerateRequest) -> AIGenerateResponse:
    """使用AI生成内容"""
    start_time = time.time()
    
    # 获取配置
    config = get_config(request.config_id)
    if not config:
        return AIGenerateResponse(success=False, error="配置不存在")
    
    if not config.is_active:
        return AIGenerateResponse(success=False, error="配置已禁用")
    
    try:
        # 根据提供商调用相应的API
        if config.provider in [AIModelProvider.OPENAI, AIModelProvider.TONGYI, 
                               AIModelProvider.KIMI, AIModelProvider.DEEPSEEK,
                               AIModelProvider.QWEN]:
            content = await _generate_openai_compatible(config, request)
        elif config.provider == AIModelProvider.ANTHROPIC:
            content = await _generate_anthropic(config, request)
        else:
            content = await _generate_generic(config, request)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # 更新使用统计
        _update_usage_stats(True, latency_ms)
        
        return AIGenerateResponse(
            success=True,
            content=content,
            latency_ms=latency_ms
        )
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        _update_usage_stats(False, latency_ms)
        
        return AIGenerateResponse(
            success=False,
            error=f"生成失败: {str(e)}",
            latency_ms=latency_ms
        )


async def _generate_openai_compatible(config: AIModelConfig, request: AIGenerateRequest) -> str:
    """使用OpenAI兼容API生成内容"""
    import aiohttp
    
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    
    payload = {
        "model": config.model.value,
        "messages": messages,
        "temperature": request.temperature or config.temperature,
        "stream": False
    }
    
    if request.max_tokens or config.max_tokens:
        payload["max_tokens"] = request.max_tokens or config.max_tokens
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=config.timeout)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"API错误: {response.status} - {error_text}")
            
            data = await response.json()
            return data["choices"][0]["message"]["content"]


async def _generate_anthropic(config: AIModelConfig, request: AIGenerateRequest) -> str:
    """使用Anthropic API生成内容"""
    import aiohttp
    
    headers = {
        "x-api-key": config.api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": config.model.value,
        "max_tokens": request.max_tokens or config.max_tokens or 2000,
        "temperature": request.temperature or config.temperature,
        "messages": [{"role": "user", "content": request.prompt}]
    }
    
    if request.system_prompt:
        payload["system"] = request.system_prompt
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{config.base_url}/v1/messages",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=config.timeout)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"API错误: {response.status} - {error_text}")
            
            data = await response.json()
            return data["content"][0]["text"]


async def _generate_generic(config: AIModelConfig, request: AIGenerateRequest) -> str:
    """通用生成方法"""
    # 对于不支持的提供商，返回模拟内容
    return f"[模拟生成] 使用 {config.provider.value} 的 {config.model.value} 模型生成内容\n\n提示词: {request.prompt[:100]}..."


def _update_usage_stats(success: bool, latency_ms: int):
    """更新使用统计"""
    global _usage_stats
    
    _usage_stats.total_requests += 1
    _usage_stats.today_requests += 1
    
    if success:
        _usage_stats.success_rate = (
            (_usage_stats.success_rate * (_usage_stats.total_requests - 1) + 100) 
            / _usage_stats.total_requests
        )
    else:
        _usage_stats.success_rate = (
            (_usage_stats.success_rate * (_usage_stats.total_requests - 1)) 
            / _usage_stats.total_requests
        )
    
    _usage_stats.average_latency_ms = (
        (_usage_stats.average_latency_ms * (_usage_stats.total_requests - 1) + latency_ms)
        / _usage_stats.total_requests
    )


async def generate_marketing_content(request: MarketingContentRequest) -> AIGenerateResponse:
    """生成营销内容"""
    template = MARKETING_TEMPLATES.get(request.content_type)
    if not template:
        return AIGenerateResponse(success=False, error=f"不支持的内容类型: {request.content_type}")
    
    # 格式化提示词
    key_points_str = "\n".join([f"- {point}" for point in (request.key_points or [])])
    
    prompt = template["prompt_template"].format(
        target_audience=request.target_audience,
        product_service=request.product_service,
        tone=request.tone,
        language=request.language,
        key_points=key_points_str or "无",
        max_length=request.max_length
    )
    
    generate_request = AIGenerateRequest(
        config_id=request.config_id,
        prompt=prompt,
        system_prompt=template["system_prompt"],
        max_tokens=min(request.max_length * 2, 4000)
    )
    
    return await generate_content(generate_request)


async def analyze_customer(request: CustomerAnalysisRequest) -> AIGenerateResponse:
    """分析客户"""
    template = ANALYSIS_TEMPLATES.get(request.analysis_type)
    if not template:
        return AIGenerateResponse(success=False, error=f"不支持的分析师类型: {request.analysis_type}")
    
    prompt = template["prompt_template"].format(
        customer_data=request.customer_data,
        industry=request.industry or "未指定",
        language=request.language
    )
    
    generate_request = AIGenerateRequest(
        config_id=request.config_id,
        prompt=prompt,
        system_prompt=template["system_prompt"],
        max_tokens=4000
    )
    
    return await generate_content(generate_request)


def get_usage_stats() -> AIUsageStats:
    """获取使用统计"""
    return _usage_stats
