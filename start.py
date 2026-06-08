#!/usr/bin/env python3
"""
Fortune SCM App - 原生窗口桌面应用
使用 pywebview 创建独立窗口，内嵌 FastAPI 服务。
"""

import os
import sys
import threading
import time
from pathlib import Path

IS_BUNDLED = getattr(sys, '_MEIPASS', None) is not None

if IS_BUNDLED:
    PROJECT_DIR = Path(sys._MEIPASS)
else:
    PROJECT_DIR = Path(__file__).parent.resolve()

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"
APP_TITLE = "Fortune SCM - 供应链营销自动化"


def start_server():
    """在后台线程启动 FastAPI 服务器。"""
    backend_dir = PROJECT_DIR / "backend"
    for p in [str(backend_dir), str(PROJECT_DIR)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(PROJECT_DIR)
    
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, log_level="warning", access_log=False)


def wait_for_server(timeout=30):
    """等待服务器启动完成。"""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    print("=" * 50)
    print(f"  🔧 {APP_TITLE}")
    print("=" * 50)
    
    mode = "bundled" if IS_BUNDLED else "development"
    print(f"📦 Mode: {mode}")
    print(f"📂 Directory: {PROJECT_DIR}")
    
    main_py = PROJECT_DIR / "backend" / "main.py"
    if not main_py.exists():
        print(f"❌ 后端文件不存在: {main_py}")
        if sys.stdin.isatty():
            input("\n按回车键退出...")
        sys.exit(1)
    
    # 启动后台服务器
    print("🚀 正在启动服务...")
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 等待服务器就绪
    print("⏳ 等待服务就绪...")
    if not wait_for_server(timeout=30):
        print("❌ 服务启动超时")
        if sys.stdin.isatty():
            input("\n按回车键退出...")
        sys.exit(1)
    
    print("✅ 服务已就绪")
    print(f"🖥️ 正在打开应用窗口...\n")
    
    # 创建原生窗口（必须在主线程）
    try:
        import webview
        
        window = webview.create_window(
            title=APP_TITLE,
            url=URL,
            width=1280,
            height=800,
            min_size=(800, 600),
            resizable=True,
            confirm_close=False,
            text_select=True,
        )
        
        # webview.start() 会阻塞直到窗口关闭
        # daemon 线程的服务器会随进程退出自动停止
        webview.start(debug=not IS_BUNDLED)
        
    except ImportError:
        print("⚠️ pywebview 未安装，回退到浏览器模式...")
        import webbrowser
        webbrowser.open(URL)
        print(f"🌐 请在浏览器中访问: {URL}")
        print("   按 Ctrl+C 退出\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    except Exception as e:
        print(f"❌ 窗口错误: {e}")
        import traceback
        traceback.print_exc()
        if sys.stdin.isatty():
            input("\n按回车键退出...")
        sys.exit(1)
    
    print("\n👋 应用已关闭")


if __name__ == "__main__":
    main()
