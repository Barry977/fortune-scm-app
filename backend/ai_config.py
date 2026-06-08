import asyncio
import time
import json
import os
from typing import Optional, Dict, List, Any
from datetime import datetime

from backend.database import get_db_ctx
from backend.ai_config_schemas import (
    AIModelConfig, AIModelConfigCreate, AIModelConfigUpdate,
    TestConnectionRequest, TestConnectionResponse,
    AIGenerateRequest, AIGenerateResponse,
    MarketingContentRequest, CustomerAnalysisRequest,
    AIUsageStats,
    MODEL_PROVIDER_MAP, MODEL_DISPLAY_NAMES, PROVIDER_DISPLAY_NAMES,
    DEFAULT_BASE_URLS
)


# ---------------------------------------------------------------------------
# Schema migration – add columns that the original init_db may not have
# ---------------------------------------------------------------------------

def _ensure_columns():
    """Add any missing columns to ai_model_configs."""
    desired = {
        "name": "TEXT",
        "model": "TEXT",
        "temperature": "REAL DEFAULT 0.7",
        "max_tokens": "INTEGER",
        "timeout": "INTEGER DEFAULT 30",
        "is_default": "INTEGER DEFAULT 0",
        "updated_at": "TIMESTAMP",
    }
    with get_db_ctx() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(ai_model_configs)").fetchall()}
        for col, typedef in desired.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE ai_model_configs ADD COLUMN {col} {typedef}")


def _init_table():
    """Create table if it doesn't exist, then ensure columns."""
    with get_db_ctx() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_model_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                base_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    _ensure_columns()


# Run on import so the table is always ready
_init_table()

# In-memory usage stats (kept simple; could be persisted later)
_usage_stats = AIUsageStats()


# ---------------------------------------------------------------------------
# Template definitions (unchanged from original)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _row_to_config(row) -> AIModelConfig:
    """Convert a sqlite3.Row to an AIModelConfig."""
    return AIModelConfig(
        id=str(row["id"]),
        name=row["name"] or f"配置-{row['id']}",
        provider=row["provider"],
        model=row["model"] or row.get("model_name", ""),
        api_key=row["api_key"],
        base_url=row["base_url"],
        temperature=row["temperature"] if row["temperature"] is not None else 0.7,
        max_tokens=row["max_tokens"],
        timeout=row["timeout"] if row["timeout"] is not None else 30,
        is_default=bool(row["is_default"]) if row["is_default"] is not None else False,
        is_active=bool(row["is_active"]) if row["is_active"] is not None else True,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _get_default_base_url(provider: str) -> str:
    """获取默认API基础URL"""
    return DEFAULT_BASE_URLS.get(provider, "")


# ---------------------------------------------------------------------------
# CRUD – SQLite backed
# ---------------------------------------------------------------------------

def create_config(config_data: AIModelConfigCreate) -> AIModelConfig:
    """创建AI配置"""
    now = datetime.now().isoformat()

    # 如果设为默认，先取消其他默认配置
    if config_data.is_default:
        with get_db_ctx() as conn:
            conn.execute("UPDATE ai_model_configs SET is_default = 0 WHERE is_default = 1")

    base_url = config_data.base_url or _get_default_base_url(config_data.provider)

    with get_db_ctx() as conn:
        cur = conn.execute(
            """INSERT INTO ai_model_configs
                   (name, provider, model_name, model, api_key, base_url,
                    temperature, max_tokens, timeout,
                    is_default, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                config_data.name,
                config_data.provider,
                config_data.model,  # model_name (NOT NULL in original schema)
                config_data.model,  # model (new column)
                config_data.api_key,
                base_url,
                config_data.temperature,
                config_data.max_tokens,
                config_data.timeout,
                1 if config_data.is_default else 0,
                now,
                now,
            ),
        )
        config_id = cur.lastrowid

    result = get_config(str(config_id))
    assert result is not None, "Config just created but not found"
    return result


def get_config(config_id: str) -> Optional[AIModelConfig]:
    """获取AI配置"""
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM ai_model_configs WHERE id = ?", (config_id,)
        ).fetchone()
    if not row:
        return None
    return _row_to_config(row)


def get_default_config() -> Optional[AIModelConfig]:
    """获取默认配置"""
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM ai_model_configs WHERE is_default = 1 AND is_active = 1 LIMIT 1"
        ).fetchone()
        if row:
            return _row_to_config(row)
        # 没有默认配置则返回第一个活跃配置
        row = conn.execute(
            "SELECT * FROM ai_model_configs WHERE is_active = 1 LIMIT 1"
        ).fetchone()
    return _row_to_config(row) if row else None


def list_configs() -> List[AIModelConfig]:
    """列出所有AI配置"""
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_model_configs ORDER BY is_default DESC, id ASC"
        ).fetchall()
    return [_row_to_config(r) for r in rows]


def update_config(config_id: str, config_data: AIModelConfigUpdate) -> Optional[AIModelConfig]:
    """更新AI配置"""
    existing = get_config(config_id)
    if not existing:
        return None

    updates = config_data.model_dump(exclude_unset=True)
    if not updates:
        return existing

    # 如果设为默认，先取消其他默认配置
    if updates.get("is_default"):
        with get_db_ctx() as conn:
            conn.execute(
                "UPDATE ai_model_configs SET is_default = 0 WHERE id != ? AND is_default = 1",
                (config_id,),
            )

    # 布尔转整数
    if "is_default" in updates:
        updates["is_default"] = 1 if updates["is_default"] else 0
    if "is_active" in updates:
        updates["is_active"] = 1 if updates["is_active"] else 0

    updates["updated_at"] = datetime.now().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [config_id]

    with get_db_ctx() as conn:
        conn.execute(
            f"UPDATE ai_model_configs SET {set_clause} WHERE id = ?", values
        )

    return get_config(config_id)


def delete_config(config_id: str) -> bool:
    """删除AI配置"""
    with get_db_ctx() as conn:
        cur = conn.execute("DELETE FROM ai_model_configs WHERE id = ?", (config_id,))
        return cur.rowcount > 0


def get_available_models() -> Dict[str, Any]:
    """获取可用模型列表（建议值）"""
    providers = {}
    for provider_id, label in PROVIDER_DISPLAY_NAMES.items():
        models = []
        for model_id, m_provider in MODEL_PROVIDER_MAP.items():
            if m_provider == provider_id:
                models.append({
                    "value": model_id,
                    "label": MODEL_DISPLAY_NAMES.get(model_id, model_id),
                    "provider": provider_id,
                })
        providers[provider_id] = {
            "label": label,
            "models": models,
            "default_base_url": DEFAULT_BASE_URLS.get(provider_id, ""),
        }
    return providers


# ---------------------------------------------------------------------------
# AI connection testing
# ---------------------------------------------------------------------------

async def test_connection(request: TestConnectionRequest) -> TestConnectionResponse:
    """测试AI连接"""
    start_time = time.time()
    try:
        if request.provider == "openai":
            success = await _test_openai(request)
        elif request.provider == "anthropic":
            success = await _test_anthropic(request)
        elif request.provider in ("tongyi", "kimi", "deepseek", "qwen"):
            success = await _test_openai_compatible(request)
        else:
            success = await _test_generic(request)

        latency_ms = int((time.time() - start_time) * 1000)
        if success:
            return TestConnectionResponse(
                success=True,
                message="连接成功",
                latency_ms=latency_ms,
                model_info={"model": request.model, "provider": request.provider},
            )
        return TestConnectionResponse(
            success=False,
            message="连接失败，请检查API密钥和配置",
            latency_ms=latency_ms,
        )
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return TestConnectionResponse(
            success=False,
            message=f"连接异常: {str(e)}",
            latency_ms=latency_ms,
        )


async def _test_openai(request: TestConnectionRequest) -> bool:
    import aiohttp
    base_url = request.base_url or DEFAULT_BASE_URLS.get("openai", "")
    headers = {"Authorization": f"Bearer {request.api_key}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{base_url}/models", headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            return resp.status == 200


async def _test_anthropic(request: TestConnectionRequest) -> bool:
    import aiohttp
    base_url = request.base_url or DEFAULT_BASE_URLS.get("anthropic", "")
    headers = {
        "x-api-key": request.api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/v1/messages", headers=headers,
            json={"model": request.model, "max_tokens": 10, "messages": [{"role": "user", "content": "Hello"}]},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            return resp.status in (200, 429)


async def _test_openai_compatible(request: TestConnectionRequest) -> bool:
    import aiohttp
    base_url = request.base_url or DEFAULT_BASE_URLS.get(request.provider, "")
    headers = {"Authorization": f"Bearer {request.api_key}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/chat/completions", headers=headers,
            json={"model": request.model, "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 5},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            return resp.status in (200, 429)


async def _test_generic(request: TestConnectionRequest) -> bool:
    return True


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

async def generate_content(request: AIGenerateRequest) -> AIGenerateResponse:
    """使用AI生成内容"""
    start_time = time.time()

    config = get_config(request.config_id)
    if not config:
        return AIGenerateResponse(success=False, error="配置不存在")
    if not config.is_active:
        return AIGenerateResponse(success=False, error="配置已禁用")

    try:
        if config.provider in ("openai", "tongyi", "kimi", "deepseek", "qwen"):
            content = await _generate_openai_compatible(config, request)
        elif config.provider == "anthropic":
            content = await _generate_anthropic(config, request)
        else:
            content = await _generate_generic(config, request)

        latency_ms = int((time.time() - start_time) * 1000)
        _update_usage_stats(True, latency_ms)
        return AIGenerateResponse(success=True, content=content, latency_ms=latency_ms)
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        _update_usage_stats(False, latency_ms)
        return AIGenerateResponse(success=False, error=f"生成失败: {str(e)}", latency_ms=latency_ms)


async def _generate_openai_compatible(config: AIModelConfig, request: AIGenerateRequest) -> str:
    import aiohttp
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}

    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})

    payload: Dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": request.temperature or config.temperature,
        "stream": False,
    }
    if request.max_tokens or config.max_tokens:
        payload["max_tokens"] = request.max_tokens or config.max_tokens

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{config.base_url}/chat/completions", headers=headers,
            json=payload, timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"API错误: {resp.status} - {error_text}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def _generate_anthropic(config: AIModelConfig, request: AIGenerateRequest) -> str:
    import aiohttp
    headers = {
        "x-api-key": config.api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload: Dict[str, Any] = {
        "model": config.model,
        "max_tokens": request.max_tokens or config.max_tokens or 2000,
        "temperature": request.temperature or config.temperature,
        "messages": [{"role": "user", "content": request.prompt}],
    }
    if request.system_prompt:
        payload["system"] = request.system_prompt

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{config.base_url}/v1/messages", headers=headers,
            json=payload, timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"API错误: {resp.status} - {error_text}")
            data = await resp.json()
            return data["content"][0]["text"]


async def _generate_generic(config: AIModelConfig, request: AIGenerateRequest) -> str:
    return f"[模拟生成] 使用 {config.provider} 的 {config.model} 模型生成内容\n\n提示词: {request.prompt[:100]}..."


def _update_usage_stats(success: bool, latency_ms: int):
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
    _usage_stats.average_latency_ms = int(
        (_usage_stats.average_latency_ms * (_usage_stats.total_requests - 1) + latency_ms)
        / _usage_stats.total_requests
    )


async def generate_marketing_content(request: MarketingContentRequest) -> AIGenerateResponse:
    """生成营销内容"""
    template = MARKETING_TEMPLATES.get(request.content_type)
    if not template:
        return AIGenerateResponse(success=False, error=f"不支持的内容类型: {request.content_type}")

    key_points_str = "\n".join([f"- {point}" for point in (request.key_points or [])])
    prompt = template["prompt_template"].format(
        target_audience=request.target_audience,
        product_service=request.product_service,
        tone=request.tone,
        language=request.language,
        key_points=key_points_str or "无",
        max_length=request.max_length,
    )

    generate_request = AIGenerateRequest(
        config_id=request.config_id,
        prompt=prompt,
        system_prompt=template["system_prompt"],
        max_tokens=min(request.max_length * 2, 4000),
    )
    return await generate_content(generate_request)


async def analyze_customer(request: CustomerAnalysisRequest) -> AIGenerateResponse:
    """分析客户"""
    template = ANALYSIS_TEMPLATES.get(request.analysis_type)
    if not template:
        return AIGenerateResponse(success=False, error=f"不支持的分析类型: {request.analysis_type}")

    prompt = template["prompt_template"].format(
        customer_data=request.customer_data,
        industry=request.industry or "未指定",
        language=request.language,
    )

    generate_request = AIGenerateRequest(
        config_id=request.config_id,
        prompt=prompt,
        system_prompt=template["system_prompt"],
        max_tokens=4000,
    )
    return await generate_content(generate_request)


def get_usage_stats() -> AIUsageStats:
    """获取使用统计"""
    return _usage_stats
