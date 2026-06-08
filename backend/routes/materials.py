from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from models import MaterialCreate
from database import get_db_ctx

router = APIRouter(prefix="/api/materials", tags=["Materials"])


@router.get("")
async def list_materials():
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM materials ORDER BY created_at DESC").fetchall()
        return {"materials": [dict(r) for r in rows]}


@router.post("/upload")
async def upload_material(material: MaterialCreate):
    with get_db_ctx() as conn:
        cur = conn.execute(
            "INSERT INTO materials (title, content, type, tags) VALUES (?, ?, ?, ?)",
            (material.title, material.content, material.type, material.tags),
        )
        return {"id": cur.lastrowid, "status": "created"}


@router.delete("/{material_id}")
async def delete_material(material_id: int):
    with get_db_ctx() as conn:
        conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        return {"status": "deleted"}
