import os
import sys
import webbrowser
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
from routes import linkedin, materials, content, email, stats, settings

app = FastAPI(title="Fortune SCM", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由（路由器已自带 /api/xxx 前缀，不要重复加）
app.include_router(linkedin.router)
app.include_router(materials.router)
app.include_router(content.router)
app.include_router(email.router)
app.include_router(stats.router)
app.include_router(settings.router)

# 静态文件 - 指向 frontend/static 目录
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
static_dir = os.path.join(frontend_dir, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup():
    """启动时初始化"""
    init_db()
    print("✅ Fortune SCM 已启动")


@app.get("/")
async def root():
    """服务前端页面"""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Fortune SCM API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
