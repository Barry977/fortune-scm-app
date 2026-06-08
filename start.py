#!/usr/bin/env python3
"""
Fortune SCM App - Launcher
Installs dependencies, starts the FastAPI server, and opens the browser.
"""

import os
import sys
import subprocess
import time
import webbrowser
import signal
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def get_python():
    """Get the Python interpreter (venv if available, else system)."""
    venv_python = VENV_DIR / "bin" / "python"
    if sys.platform == "win32":
        venv_python = VENV_DIR / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def get_pip():
    """Get the pip executable."""
    venv_pip = VENV_DIR / "bin" / "pip"
    if sys.platform == "win32":
        venv_pip = VENV_DIR / "Scripts" / "pip.exe"
    if venv_pip.exists():
        return str(venv_pip)
    return "pip3"


def create_venv():
    """Create virtual environment if it doesn't exist."""
    if VENV_DIR.exists():
        return
    print("📦 Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    print("✅ Virtual environment created.")


def install_deps():
    """Install dependencies from requirements.txt."""
    python = get_python()
    pip = get_pip()

    # Check if we need to install
    marker = PROJECT_DIR / ".deps_installed"
    req_mtime = REQUIREMENTS.stat().st_mtime if REQUIREMENTS.exists() else 0
    if marker.exists() and marker.stat().st_mtime >= req_mtime:
        print("✅ Dependencies already installed.")
        return

    print("📦 Installing dependencies...")
    subprocess.run(
        [python, "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [python, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        check=True,
    )
    marker.touch()
    print("✅ Dependencies installed.")


def install_playwright_browsers():
    """Install Playwright browser binaries if needed."""
    python = get_python()
    try:
        subprocess.run(
            [python, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
        )
        print("✅ Playwright browsers ready.")
    except subprocess.CalledProcessError:
        print("⚠️  Playwright browser install failed. LinkedIn automation may not work.")


def find_main_module():
    """Find the main FastAPI app module."""
    candidates = [
        PROJECT_DIR / "backend" / "main.py",
        PROJECT_DIR / "main.py",
        PROJECT_DIR / "app.py",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fallback: look for 'app' in any Python file
    for f in PROJECT_DIR.glob("*.py"):
        text = f.read_text()
        if "FastAPI" in text and "app" in text:
            return f
    return None


def main():
    os.chdir(PROJECT_DIR)
    print("=" * 50)
    print("  🚀 Fortune SCM App")
    print("=" * 50)

    # Step 1: Create venv & install deps
    create_venv()
    install_deps()

    # Step 2: Install Playwright
    install_playwright_browsers()

    # Step 3: Start server
    python = get_python()
    main_module = find_main_module()

    # Add project root to PYTHONPATH so content_engine.py is importable
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    if main_module:
        backend_dir = main_module.parent  # e.g. backend/
        # When running from backend/ dir, internal imports (database, routes, services) work
        # PYTHONPATH includes project root so content_engine.py is importable
        cmd = [python, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT), "--reload"]
        run_cwd = str(backend_dir)
    else:
        # Inline minimal server if no main module found
        print("⚠️  No main module found. Creating minimal server...")
        create_minimal_server()
        cmd = [python, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT), "--reload"]
        run_cwd = str(PROJECT_DIR)

    print(f"\n🌐 Starting server at {URL}")
    print("   Press Ctrl+C to stop\n")

    # Open browser after a short delay
    import threading

    def open_browser():
        time.sleep(2)
        webbrowser.open(URL)

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Run server
    try:
        subprocess.run(cmd, cwd=run_cwd, env=env)
    except KeyboardInterrupt:
        print("\n👋 Shutting down Fortune SCM App...")
        sys.exit(0)


def create_minimal_server():
    """Create a minimal FastAPI main.py if none exists."""
    main_py = PROJECT_DIR / "main.py"
    if main_py.exists():
        return

    content = '''"""
Fortune SCM App - Main Server
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import json
import uvicorn

from content_engine import (
    init_db, start_scheduler, stop_scheduler,
    upload_material, list_materials, get_material, delete_material, search_materials, all_tags,
    generate_post, list_posts, get_post, update_post, delete_post, preview_post,
    update_schedule,
)

app = FastAPI(title="Fortune SCM App", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.on_event("startup")
async def startup():
    init_db()
    start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()


# ── Materials API ─────────────────────────────────────────────────

@app.get("/api/materials")
async def api_list_materials(
    tag: str = Query(None),
    search: str = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    return list_materials(tag=tag, search=search, limit=limit, offset=offset)


@app.post("/api/materials/upload")
async def api_upload_material(
    title: str = Form(...),
    content: str = Form(""),
    type: str = Form("text"),
    tags: str = Form("[]"),
    file: UploadFile = File(None),
):
    tag_list = json.loads(tags) if tags else []
    file_bytes = await file.read() if file else None
    filename = file.filename if file else None
    material = upload_material(
        title=title, content=content, material_type=type,
        tags=tag_list, file_bytes=file_bytes, filename=filename,
    )
    return material


@app.delete("/api/materials/{material_id}")
async def api_delete_material(material_id: int):
    if not delete_material(material_id):
        raise HTTPException(404, "Material not found")
    return {"ok": True}


@app.get("/api/materials/tags")
async def api_all_tags():
    return all_tags()


# ── Content Generation API ────────────────────────────────────────

@app.post("/api/content/generate")
async def api_generate(body: dict):
    material_ids = body.get("material_ids", [])
    custom_prompt = body.get("custom_prompt")
    post = await generate_post(material_ids=material_ids, custom_prompt=custom_prompt)
    return post


@app.get("/api/content/preview/{post_id}")
async def api_preview(post_id: int):
    post = preview_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@app.get("/api/content/posts")
async def api_list_posts(status: str = Query(None)):
    return list_posts(status=status)


@app.put("/api/content/posts/{post_id}")
async def api_update_post(post_id: int, body: dict):
    return update_post(post_id, **body)


@app.delete("/api/content/posts/{post_id}")
async def api_delete_post(post_id: int):
    if not delete_post(post_id):
        raise HTTPException(404, "Post not found")
    return {"ok": True}


@app.post("/api/content/publish/{post_id}")
async def api_publish(post_id: int):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    # Actual LinkedIn publishing would go here
    updated = update_post(post_id, status="published", published_at=__import__("datetime").datetime.now().isoformat())
    return updated


# ── Settings API ──────────────────────────────────────────────────

@app.get("/api/settings")
async def api_get_settings():
    import sqlite3
    from content_engine import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


@app.put("/api/settings")
async def api_update_settings(body: dict):
    import sqlite3
    from content_engine import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    for k, v in body.items():
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Stats API ─────────────────────────────────────────────────────

@app.get("/api/stats/daily")
async def api_daily_stats():
    import sqlite3
    conn = sqlite3.connect("fortune_scm.db")
    conn.row_factory = sqlite3.Row
    today = __import__("datetime").date.today().isoformat()
    materials = conn.execute("SELECT COUNT(*) as c FROM materials WHERE date(created_at) = ?", (today,)).fetchone()["c"]
    posts = conn.execute("SELECT COUNT(*) as c FROM posts WHERE date(created_at) = ?", (today,)).fetchone()["c"]
    published = conn.execute("SELECT COUNT(*) as c FROM posts WHERE status='published' AND date(published_at) = ?", (today,)).fetchone()["c"]
    conn.close()
    return {"materials_added": materials, "posts_generated": posts, "posts_published": published}


@app.get("/api/stats/customers")
async def api_customers():
    import sqlite3
    conn = sqlite3.connect("fortune_scm.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM customers ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Health ────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Fortune SCM"}


@app.get("/", response_class=HTMLResponse)
async def root():
    index = FRONTEND_DIR / "index.html" if FRONTEND_DIR.exists() else None
    if index and index.exists():
        return index.read_text()
    return "<h1>Fortune SCM App</h1><p>Frontend not found. Place index.html in frontend/</p>"
'''
    main_py.write_text(content)
    print("✅ Created minimal main.py")


if __name__ == "__main__":
    main()
