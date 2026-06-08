from fastapi import APIRouter
from models import SettingsUpdate
from database import get_db_ctx

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
async def get_settings():
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    settings = {}
    for r in rows:
        val = r["value"]
        if r["key"] in ("smtp_password", "ai_api_key") and val:
            val = val[:4] + "****"
        settings[r["key"]] = val
    return settings


@router.put("")
async def update_settings(body: SettingsUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    with get_db_ctx() as conn:
        for k, v in updates.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
    return {"status": "updated", "updated_keys": list(updates.keys())}
