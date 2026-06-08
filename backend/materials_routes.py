"""素材库 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.materials import (
    create_material, get_material, list_materials,
    update_material, delete_material, increment_usage,
    get_categories, get_stats
)

router = APIRouter(prefix="/api/materials", tags=["素材库"])


class MaterialCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: str = Field("general", max_length=50)
    tags: str = Field("", max_length=500)
    type: str = Field("text", max_length=20)
    language: str = Field("en", max_length=10)
    is_shared: bool = True


class MaterialUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    is_shared: Optional[bool] = None


@router.get("/")
async def api_list_materials(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(get_current_user)
):
    """列出所有共享素材"""
    return list_materials(category=category, search=search, limit=limit)


@router.get("/categories")
async def api_get_categories(current_user=Depends(get_current_user)):
    """获取素材分类列表"""
    return {"categories": get_categories()}


@router.get("/stats")
async def api_get_stats(current_user=Depends(get_current_user)):
    """素材库统计"""
    return get_stats()


@router.get("/{material_id}")
async def api_get_material(material_id: int, current_user=Depends(get_current_user)):
    """获取单个素材"""
    m = get_material(material_id)
    if not m:
        raise HTTPException(status_code=404, detail="素材不存在")
    return m


@router.post("/")
async def api_create_material(data: MaterialCreate, current_user=Depends(get_current_user)):
    """创建素材"""
    m = create_material({**data.model_dump(), "created_by": current_user.id})
    return m


@router.put("/{material_id}")
async def api_update_material(material_id: int, data: MaterialUpdate, current_user=Depends(get_current_user)):
    """更新素材"""
    m = update_material(material_id, data.model_dump(exclude_unset=True))
    if not m:
        raise HTTPException(status_code=404, detail="素材不存在")
    return m


@router.delete("/{material_id}")
async def api_delete_material(material_id: int, current_user=Depends(get_current_user)):
    """删除素材"""
    if not delete_material(material_id):
        raise HTTPException(status_code=404, detail="素材不存在")
    return {"message": "已删除"}


@router.post("/{material_id}/use")
async def api_use_material(material_id: int, current_user=Depends(get_current_user)):
    """记录素材使用次数"""
    increment_usage(material_id)
    return {"message": "已记录"}
