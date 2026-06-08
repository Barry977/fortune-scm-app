"""
素材库模块 — 全局共享，所有用户可用
存储营销素材：文本模板、图片链接、话术库、案例库等
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from backend.database import get_db_ctx


def _init_table():
    with get_db_ctx() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '',
                type TEXT DEFAULT 'text',
                language TEXT DEFAULT 'en',
                is_shared INTEGER DEFAULT 1,
                created_by INTEGER,
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

_init_table()


def create_material(data: dict) -> dict:
    """创建素材（全局共享）"""
    now = datetime.utcnow().isoformat()
    with get_db_ctx() as conn:
        cur = conn.execute(
            """INSERT INTO materials (title, content, category, tags, type, language, is_shared, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['title'], data['content'],
             data.get('category', 'general'),
             data.get('tags', ''),
             data.get('type', 'text'),
             data.get('language', 'en'),
             data.get('is_shared', 1),
             data.get('created_by'),
             now, now)
        )
        mid = cur.lastrowid
    return get_material(mid)


def get_material(material_id: int) -> Optional[dict]:
    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    return dict(row) if row else None


def list_materials(category: str = None, search: str = None, limit: int = 100) -> List[dict]:
    """列出所有共享素材（不限用户）"""
    query = "SELECT * FROM materials WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
        params.extend([f'%{search}%'] * 3)
    query += " ORDER BY usage_count DESC, updated_at DESC LIMIT ?"
    params.append(limit)
    with get_db_ctx() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_material(material_id: int, data: dict) -> Optional[dict]:
    sets = ["updated_at = ?"]
    params = [datetime.utcnow().isoformat()]
    for field in ['title', 'content', 'category', 'tags', 'type', 'language', 'is_shared']:
        if field in data and data[field] is not None:
            sets.append(f"{field} = ?")
            params.append(data[field])
    params.append(material_id)
    with get_db_ctx() as conn:
        conn.execute(f"UPDATE materials SET {', '.join(sets)} WHERE id = ?", params)
    return get_material(material_id)


def delete_material(material_id: int) -> bool:
    with get_db_ctx() as conn:
        cur = conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))
    return cur.rowcount > 0


def increment_usage(material_id: int):
    with get_db_ctx() as conn:
        conn.execute("UPDATE materials SET usage_count = usage_count + 1 WHERE id = ?", (material_id,))


def get_categories() -> List[str]:
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM materials ORDER BY category").fetchall()
    return [r['category'] for r in rows]


def get_stats() -> dict:
    with get_db_ctx() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM materials").fetchone()['c']
        by_cat = conn.execute("SELECT category, COUNT(*) as c FROM materials GROUP BY category").fetchall()
    return {
        "total": total,
        "by_category": {r['category']: r['c'] for r in by_cat},
    }


def seed_default_materials():
    """预置默认素材"""
    defaults = [
        {"title": "Cold Outreach - Introduction", "content": "Hi {name},\n\nI came across your profile at {company} and was impressed by your work in {industry}.\n\nAt Fortune SCM, we specialize in international logistics — air freight, DDU delivery, and supply chain solutions for businesses like yours.\n\nWould you be open to a brief conversation about how we might support your logistics needs?\n\nBest regards,\nBarry Yang", "category": "cold_email", "tags": "introduction,cold,email", "type": "text", "language": "en"},
        {"title": "LinkedIn Connection Note", "content": "Hi, I would like to connect regarding logistics and supply chain solutions.", "category": "linkedin", "tags": "connection,note", "type": "text", "language": "en"},
        {"title": "LinkedIn Follow-up Message", "content": "Hi {name},\n\nThanks for connecting! I noticed your work at {company} and thought there might be synergy.\n\nWe help companies streamline their international shipping — particularly air freight from China to the US, Europe, and Middle East with DDU delivery.\n\nWould you be interested in learning more?", "category": "linkedin", "tags": "follow-up,message", "type": "text", "language": "en"},
        {"title": "Quote Follow-up", "content": "Hi {name},\n\nI wanted to follow up on the quote we discussed for {company}. Our air freight rates remain competitive, and we can guarantee 3-5 day door-to-door delivery.\n\nWould you like to move forward, or do you have any questions about the pricing?\n\nBest,\nBarry", "category": "follow_up", "tags": "quote,follow-up", "type": "text", "language": "en"},
        {"title": "Price Inquiry Reply", "content": "Thank you for your interest! I'd be happy to discuss pricing for your logistics needs.\n\nCould you share:\n- Origin and destination\n- Cargo type and weight/volume\n- Preferred timeline\n\nThis will help me provide an accurate quote.\n\nBest regards,\nBarry Yang", "category": "reply", "tags": "price,quote,inquiry", "type": "text", "language": "en"},
        {"title": "开发信 - 中文版", "content": "{name} 您好，\n\n我是 Fortune SCM 的 Barry Yang，专注于国际物流和供应链解决方案。\n\n我们擅长中国到欧美/中东的空运服务，提供DDU门到门交付，3-5天到达。\n\n如果您有国际物流方面的需求，期待有机会合作。\n\n此致\nBarry Yang", "category": "cold_email", "tags": "introduction,chinese", "type": "text", "language": "zh"},
    ]
    with get_db_ctx() as conn:
        existing = conn.execute("SELECT COUNT(*) as c FROM materials").fetchone()['c']
        if existing > 0:
            return
        for d in defaults:
            now = datetime.utcnow().isoformat()
            conn.execute(
                "INSERT INTO materials (title, content, category, tags, type, language, is_shared, created_at, updated_at) VALUES (?,?,?,?,?,?,1,?,?)",
                (d['title'], d['content'], d['category'], d['tags'], d['type'], d['language'], now, now)
            )
