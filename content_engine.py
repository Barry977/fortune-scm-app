"""
Fortune SCM App - Content Engine Module
Handles material library management, AI post generation, and scheduling.
"""

import os
import json
import sqlite3
import random
import hashlib
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


# ── Database helper ──────────────────────────────────────────────────────────

# Align with existing backend: data/fortune.db relative to project root
_PROJECT_ROOT = Path(__file__).parent.resolve()
_DEFAULT_DB = str(_PROJECT_ROOT / "data" / "fortune.db")
DB_PATH = os.getenv("FORTUNE_DB", _DEFAULT_DB)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create all required tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS materials (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'text',   -- text | image
            tags        TEXT DEFAULT '[]',              -- JSON array of strings
            file_path   TEXT,                           -- local path for image files
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS posts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            content          TEXT NOT NULL,
            material_ids     TEXT DEFAULT '[]',          -- JSON array of source material IDs
            ai_model         TEXT,
            status           TEXT NOT NULL DEFAULT 'draft',  -- draft | scheduled | published | failed
            scheduled_at     TEXT,
            published_at     TEXT,
            linkedin_post_id TEXT,
            engagement_stats TEXT DEFAULT '{}',
            created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT,
            company      TEXT,
            title        TEXT,
            linkedin_url TEXT,
            email        TEXT,
            status       TEXT DEFAULT 'new',
            notes        TEXT DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)
    # Seed default settings
    defaults = {
        "ai_provider": "openai",
        "ai_model": "gpt-4o-mini",
        "ai_api_key": "",
        "ai_base_url": "",
        "publish_time": "09:00",
        "daily_post_limit": "1",
        "auto_publish": "false",
    }
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
        )
    conn.commit()
    conn.close()


# ── Material Library ─────────────────────────────────────────────────────────

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def upload_material(
    title: str,
    content: str,
    material_type: str = "text",
    tags: Optional[list[str]] = None,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
) -> dict:
    """Upload a new material (text or image) into the library."""
    tags = tags or []
    file_path = None

    if material_type == "image" and file_bytes and filename:
        ext = Path(filename).suffix or ".png"
        safe_name = hashlib.md5(f"{datetime.now().isoformat()}{filename}".encode()).hexdigest()[:12]
        file_path = str(UPLOAD_DIR / f"{safe_name}{ext}")
        Path(file_path).write_bytes(file_bytes)

    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO materials (title, content, type, tags, file_path)
           VALUES (?, ?, ?, ?, ?)""",
        (title, content, material_type, json.dumps(tags, ensure_ascii=False), file_path),
    )
    material_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    conn.close()
    return dict(row)


def list_materials(
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List materials with optional tag filter and text search."""
    conn = _get_db()
    query = "SELECT * FROM materials WHERE 1=1"
    params: list = []

    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag}%")
    if search:
        query += " AND (title LIKE ? OR content LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_material(material_id: int) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_material(material_id: int) -> bool:
    conn = _get_db()
    row = conn.execute("SELECT file_path FROM materials WHERE id = ?", (material_id,)).fetchone()
    if row and row["file_path"]:
        p = Path(row["file_path"])
        if p.exists():
            p.unlink()
    cur = conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def search_materials(keyword: str) -> list[dict]:
    """Full-text search across title, content, and tags."""
    return list_materials(search=keyword)


def all_tags() -> list[str]:
    """Return a deduplicated list of all tags in the library."""
    conn = _get_db()
    rows = conn.execute("SELECT tags FROM materials").fetchall()
    conn.close()
    tags: set[str] = set()
    for r in rows:
        try:
            tags.update(json.loads(r["tags"]))
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(tags)


# ── AI Post Generation ───────────────────────────────────────────────────────

def _get_ai_settings() -> dict:
    conn = _get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


async def generate_post(
    material_ids: list[int],
    custom_prompt: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """
    Generate a LinkedIn post from 1-3 materials using AI.
    Returns a dict with the generated content and metadata.
    """
    if not material_ids or len(material_ids) > 3:
        raise ValueError("Please select 1-3 materials for post generation.")

    # Fetch materials
    materials = []
    for mid in material_ids:
        m = get_material(mid)
        if not m:
            raise ValueError(f"Material {mid} not found.")
        materials.append(m)

    # AI settings (override or from DB)
    settings = _get_ai_settings()
    provider = provider or settings.get("ai_provider", "openai")
    model = model or settings.get("ai_model", "gpt-4o-mini")
    api_key = api_key or settings.get("ai_api_key", "")
    base_url = base_url or settings.get("ai_base_url", "")

    if not api_key and provider in ("openai", "anthropic"):
        raise ValueError("AI API key not configured. Please set it in Settings.")

    # Build prompt
    material_text = ""
    for i, m in enumerate(materials, 1):
        material_text += f"\n--- Material {i}: {m['title']} ---\n{m['content']}\n"

    system_prompt = """You are a LinkedIn content expert specializing in logistics and supply chain management (SCM) B2B marketing. 
Generate an engaging LinkedIn post based on the provided materials.

Rules:
- Write in English (or match the language of the materials)
- Keep it professional but approachable
- Include a compelling hook in the first line
- Use line breaks for readability
- End with a call-to-action or question to drive engagement
- Add 3-5 relevant hashtags at the end
- Keep total length under 1300 characters
- Do NOT include emojis excessively (1-2 max)"""

    user_prompt = f"""Generate a LinkedIn post based on these materials:

{material_text}

{"Additional instructions: " + custom_prompt if custom_prompt else "Generate an engaging post that highlights the value proposition."}"""

    # Call AI
    generated_content = await _call_ai(provider, model, api_key, base_url, system_prompt, user_prompt)

    # Save as draft post
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO posts (content, material_ids, ai_model, status)
           VALUES (?, ?, ?, 'draft')""",
        (generated_content, json.dumps(material_ids), f"{provider}/{model}"),
    )
    post_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()

    return dict(row)


async def _call_ai(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call the configured AI provider and return the generated text."""
    if provider == "openai":
        return await _call_openai_compatible(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    elif provider == "anthropic":
        return await _call_anthropic(api_key, model, system_prompt, user_prompt)
    elif provider == "custom":
        # Custom endpoint must be OpenAI-compatible
        if not base_url:
            raise ValueError("Custom AI provider requires a base_url.")
        return await _call_openai_compatible(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")


async def _call_openai_compatible(
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call any OpenAI-compatible API (OpenAI, DeepSeek, local models, etc.)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 1000,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _call_anthropic(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call the Anthropic (Claude) API."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


# ── Post Management ──────────────────────────────────────────────────────────

def list_posts(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    conn = _get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_post(post_id: int) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_post(post_id: int, **kwargs) -> Optional[dict]:
    """Update post fields (content, status, scheduled_at, etc.)."""
    conn = _get_db()
    allowed = {"content", "status", "scheduled_at", "published_at", "engagement_stats"}
    sets, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        conn.close()
        return get_post(post_id)
    vals.append(post_id)
    conn.execute(f"UPDATE posts SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return get_post(post_id)


def delete_post(post_id: int) -> bool:
    conn = _get_db()
    cur = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def preview_post(post_id: int) -> Optional[dict]:
    """Preview a draft/scheduled post."""
    post = get_post(post_id)
    if post:
        post["materials"] = []
        try:
            mids = json.loads(post.get("material_ids", "[]"))
            for mid in mids:
                m = get_material(mid)
                if m:
                    post["materials"].append({"id": m["id"], "title": m["title"]})
        except (json.JSONDecodeError, TypeError):
            pass
    return post


# ── Scheduling ───────────────────────────────────────────────────────────────

_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler():
    """Start the APScheduler for daily auto-generation and publishing."""
    scheduler = get_scheduler()

    # Auto-generate post daily
    scheduler.add_job(
        _daily_generate_job,
        CronTrigger(hour=8, minute=0),  # Generate at 8 AM
        id="daily_generate",
        replace_existing=True,
        name="Daily Post Generation",
    )

    # Auto-publish scheduled posts
    scheduler.add_job(
        _daily_publish_job,
        CronTrigger(hour=9, minute=0),  # Publish at 9 AM (configurable)
        id="daily_publish",
        replace_existing=True,
        name="Daily Post Publishing",
    )

    scheduler.start()
    print("[ContentEngine] Scheduler started — generate at 08:00, publish at 09:00")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[ContentEngine] Scheduler stopped")


def _daily_generate_job():
    """Pick random materials and generate a draft post."""
    import asyncio

    settings = _get_ai_settings()
    if settings.get("auto_publish", "false") != "true":
        return

    materials = list_materials(limit=100)
    if not materials:
        print("[Scheduler] No materials available for generation.")
        return

    # Pick 1-3 random materials
    count = min(random.randint(1, 3), len(materials))
    chosen = random.sample(materials, count)
    ids = [m["id"] for m in chosen]

    try:
        loop = asyncio.new_event_loop()
        post = loop.run_until_complete(generate_post(material_ids=ids))
        loop.close()
        print(f"[Scheduler] Generated draft post #{post['id']} from materials {ids}")
    except Exception as e:
        print(f"[Scheduler] Generation failed: {e}")


def _daily_publish_job():
    """Publish the oldest draft/scheduled post."""
    settings = _get_ai_settings()
    if settings.get("auto_publish", "false") != "true":
        return

    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM posts WHERE status IN ('draft','scheduled') ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    conn.close()

    if not row:
        print("[Scheduler] No posts ready to publish.")
        return

    post = dict(row)
    # Mark as published (actual LinkedIn publishing handled by linkedin_automation module)
    update_post(post["id"], status="published", published_at=datetime.now().isoformat())
    print(f"[Scheduler] Published post #{post['id']}")


def update_schedule(generate_hour: int = 8, publish_hour: int = 9):
    """Update the scheduler timing."""
    scheduler = get_scheduler()

    if scheduler.get_job("daily_generate"):
        scheduler.reschedule_job(
            "daily_generate",
            trigger=CronTrigger(hour=generate_hour, minute=0),
        )

    if scheduler.get_job("daily_publish"):
        scheduler.reschedule_job(
            "daily_publish",
            trigger=CronTrigger(hour=publish_hour, minute=0),
        )

    print(f"[ContentEngine] Schedule updated: generate at {generate_hour:02d}:00, publish at {publish_hour:02d}:00")
