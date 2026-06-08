from fastapi import APIRouter, HTTPException
from models import ContentGenerate, PostCreate
from database import get_db_ctx
from services import ai_service, linkedin_service

router = APIRouter(prefix="/api/content", tags=["Content"])


@router.post("/generate")
async def generate(body: ContentGenerate):
    with get_db_ctx() as conn:
        settings = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings").fetchall()}

    materials_text = ""
    if body.material_ids:
        with get_db_ctx() as conn:
            ids = ",".join(str(i) for i in body.material_ids)
            rows = conn.execute(f"SELECT title, content FROM materials WHERE id IN ({ids})").fetchall()
            materials_text = "\n\n".join(f"【{r['title']}】\n{r['content']}" for r in rows)

    ref_section = ("Reference materials:\n" + materials_text) if materials_text else ""
    instr_section = ("Additional instructions: " + body.prompt) if body.prompt else ""
    newline = "\n"
    prompt = f"Generate {body.count} LinkedIn post(s) for a logistics/supply chain professional.\nTone: {body.tone}\n{ref_section}{newline if ref_section else ''}{instr_section}{newline if instr_section else ''}Return only the post content, no explanations."

    try:
        result = await ai_service.generate_content(
            prompt,
            provider=settings.get("ai_provider", "openai"),
            api_key=settings.get("ai_api_key", ""),
            model=settings.get("ai_model", "gpt-4o"),
            base_url=settings.get("ai_base_url", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

    # Save as draft
    with get_db_ctx() as conn:
        conn.execute("INSERT INTO posts (content, status) VALUES (?, 'draft')", (result,))

    return {"content": result, "status": "draft"}


@router.get("/preview")
async def preview():
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM posts WHERE status = 'draft' ORDER BY id DESC LIMIT 10").fetchall()
        return {"posts": [dict(r) for r in rows]}


@router.post("/publish")
async def publish(post_id: int = None, content: str = None):
    with get_db_ctx() as conn:
        if post_id:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Post not found")
            content = row["content"]

    if not content:
        raise HTTPException(status_code=400, detail="No content to publish")

    result = await linkedin_service.publish_post(content)

    with get_db_ctx() as conn:
        if post_id:
            conn.execute("UPDATE posts SET status = 'published', published_at = CURRENT_TIMESTAMP WHERE id = ?", (post_id,))
        else:
            conn.execute("INSERT INTO posts (content, status, published_at) VALUES (?, 'published', CURRENT_TIMESTAMP)", (content,))

    return {"status": "published", "linkedin_result": result}
