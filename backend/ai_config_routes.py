from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional

from backend.auth import get_current_user, get_current_admin
from backend.ai_config import (
    create_config, get_config, update_config, delete_config,
    list_configs, get_default_config, test_connection,
    generate_content, generate_marketing_content, analyze_customer,
    get_usage_stats, get_available_models
)
from backend.ai_config_schemas import (
    AIModelConfig, AIModelConfigCreate, AIModelConfigUpdate,
    TestConnectionRequest, TestConnectionResponse,
    AIGenerateRequest, AIGenerateResponse,
    MarketingContentRequest, CustomerAnalysisRequest,
    AIUsageStats
)

router = APIRouter(prefix="/api/ai-config", tags=["AI配置"])


@router.get("/providers")
async def get_providers():
    """获取支持的模型提供商列表"""
    return get_available_models()


@router.post("/models", response_model=AIModelConfig)
async def create_model_config(
    config_data: AIModelConfigCreate,
    current_user=Depends(get_current_user)
):
    """添加AI模型配置"""
    try:
        config = create_config(config_data)
        return config
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/models", response_model=List[AIModelConfig])
async def list_model_configs(
    current_user=Depends(get_current_user)
):
    """获取所有AI模型配置"""
    return list_configs()


@router.get("/models/{config_id}", response_model=AIModelConfig)
async def get_model_config(
    config_id: str,
    current_user=Depends(get_current_user)
):
    """获取指定配置"""
    config = get_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return config


@router.put("/models/{config_id}", response_model=AIModelConfig)
async def update_model_config(
    config_id: str,
    config_data: AIModelConfigUpdate,
    current_user=Depends(get_current_user)
):
    """更新AI模型配置"""
    config = update_config(config_id, config_data)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return config


@router.delete("/models/{config_id}")
async def delete_model_config(
    config_id: str,
    current_user=Depends(get_current_user)
):
    """删除AI模型配置"""
    success = delete_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"message": "删除成功"}


@router.post("/test", response_model=TestConnectionResponse)
async def test_model_connection(
    request: TestConnectionRequest,
    current_user=Depends(get_current_user)
):
    """测试AI连接"""
    try:
        result = await test_connection(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=AIGenerateResponse)
async def generate_ai_content(
    request: AIGenerateRequest,
    current_user=Depends(get_current_user)
):
    """生成内容"""
    try:
        result = await generate_content(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/marketing", response_model=AIGenerateResponse)
async def generate_marketing(
    request: MarketingContentRequest,
    current_user=Depends(get_current_user)
):
    """生成营销内容"""
    try:
        result = await generate_marketing_content(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/analysis", response_model=AIGenerateResponse)
async def generate_analysis(
    request: CustomerAnalysisRequest,
    current_user=Depends(get_current_user)
):
    """客户分析"""
    try:
        result = await analyze_customer(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=AIUsageStats)
async def get_ai_stats(
    current_user=Depends(get_current_admin)
):
    """获取AI使用统计（仅管理员）"""
    return get_usage_stats()
