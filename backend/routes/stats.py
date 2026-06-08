from fastapi import APIRouter
from database import get_db_ctx

router = APIRouter(prefix="/api/stats", tags=["Stats"])


@router.get("/daily")
async def daily_stats():
    with get_db_ctx() as conn:
        customers = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()["c"]
        posts = conn.execute("SELECT COUNT(*) as c FROM posts WHERE status='published'").fetchone()["c"]
        drafts = conn.execute("SELECT COUNT(*) as c FROM posts WHERE status='draft'").fetchone()["c"]
        materials = conn.execute("SELECT COUNT(*) as c FROM materials").fetchone()["c"]
    return {
        "total_customers": customers,
        "published_posts": posts,
        "draft_posts": drafts,
        "total_materials": materials,
    }


@router.get("/customers")
async def list_customers(page: int = 1, limit: int = 50, status: str = None):
    offset = (page - 1) * limit
    with get_db_ctx() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM customers WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) as c FROM customers WHERE status=?", (status,)).fetchone()["c"]
        else:
            rows = conn.execute(
                "SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()["c"]
    return {"customers": [dict(r) for r in rows], "total": total, "page": page}
