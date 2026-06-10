#!/usr/bin/env python3
"""
Fortune SCM App - 原生窗口桌面应用
使用 pywebview 创建独立窗口，内嵌 FastAPI 服务。
"""

import os
import sys
import threading
import time
import json
import traceback
import logging
from pathlib import Path

# ── 日志文件 ───────────────────────────────────────────────────
if sys.platform == "win32":
    LOG_DIR = Path(os.environ.get("APPDATA", "")) / ".destiny"
else:
    LOG_DIR = Path.home() / ".destiny"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "destiny.log"

# 只写文件，不输出到 stdout（避免控制台刷屏）
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_file_handler],
)
logger = logging.getLogger("destiny")

# 抑制第三方库的 debug 日志
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

IS_BUNDLED = getattr(sys, '_MEIPASS', None) is not None

if IS_BUNDLED:
    PROJECT_DIR = Path(sys._MEIPASS)
else:
    PROJECT_DIR = Path(__file__).parent.resolve()

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"
APP_TITLE = "命运 (DESTINY) - 智能客户开发系统"
APP_ICON = str(PROJECT_DIR / "frontend" / "assets" / "icon.png") if (PROJECT_DIR / "frontend" / "assets" / "icon.png").exists() else None

def show_error_dialog(title, message):
    """Show error dialog that works even if pywebview isn't available.
    Tries multiple methods: ctypes MessageBox → tkinter → file on desktop.
    """
    # Always write to log file first
    logger.error("ERROR [%s]: %s", title, message)
    
    # Also write to desktop file as absolute fallback
    try:
        if sys.platform == "win32":
            desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        else:
            desktop = Path.home() / "Desktop"
        crash_file = desktop / "Destiny-错误报告.txt"
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write(f"命运 (DESTINY) 启动错误\n{'='*50}\n\n")
            f.write(f"标题: {title}\n\n{message}\n\n")
            f.write(f"{'='*50}\nPython: {sys.version}\n平台: {sys.platform}\n")
            f.write(f"路径: {sys.executable}\n打包: {IS_BUNDLED}\n")
    except Exception:
        pass
    
    # Method 1: Windows MessageBox (most reliable for GUI apps)
    if sys.platform == "win32":
        try:
            import ctypes
            # MB_OK | MB_ICONERROR | MB_TOPMOST | MB_SETFOREGROUND
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x1000 | 0x10 | 0x40000)
            return
        except Exception:
            pass
    
    # Method 2: tkinter (cross-platform fallback)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showerror(title, message)
        root.destroy()
        return
    except Exception:
        pass
    
    # Method 3: Last resort - print (will go to void with console=False,
    # but at least the desktop file was written above)
    print(f"\n{'='*50}")
    print(f"ERROR: {title}")
    print(f"{'='*50}")
    print(message)
    print(f"{'='*50}")


class DestinyApp:
    """桌面应用主类"""
    
    def __init__(self):
        self.window = None
        self.server_thread = None
        self.is_logged_in = False
        self.current_user = None
        self.server_error = None  # Capture server thread errors
    
    def start_server(self):
        """在后台线程启动 FastAPI 服务器。"""
        try:
            # Fix: PyInstaller console=False sets stdout/stderr to None
            # uvicorn needs them for logging, so restore them
            import io
            if sys.stdout is None:
                sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
            if sys.stderr is None:
                sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')

            backend_dir = PROJECT_DIR / "backend"
            for p in [str(backend_dir), str(PROJECT_DIR)]:
                if p not in sys.path:
                    sys.path.insert(0, p)
            os.chdir(PROJECT_DIR)
            
            logger.info("Starting uvicorn server on %s:%s", HOST, PORT)
            import uvicorn
            # Import app object directly (reliable in PyInstaller bundles)
            from backend.main import app as fastapi_app
            logger.info("FastAPI app imported successfully")
            config = uvicorn.Config(fastapi_app, host=HOST, port=PORT, log_level="warning", access_log=False)
            server = uvicorn.Server(config)
            server.run()
        except Exception as e:
            self.server_error = f"{e}\n\n{traceback.format_exc()}"
            logger.error("Server thread error: %s", self.server_error)
    
    def wait_for_server(self, timeout=30):
        """等待服务器启动完成。"""
        import urllib.request
        start = time.time()
        while time.time() - start < timeout:
            try:
                urllib.request.urlopen(f"{URL}/api/health", timeout=1)
                return True
            except Exception:
                time.sleep(0.3)
        return False
    
    def check_login_status(self):
        """检查登录状态"""
        try:
            import urllib.request
            # 尝试从本地存储获取token
            token = self.get_stored_token()
            if not token:
                return False
            
            req = urllib.request.Request(
                f"{URL}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            response = urllib.request.urlopen(req, timeout=2)
            if response.status == 200:
                data = json.loads(response.read())
                self.current_user = data
                self.is_logged_in = True
                return True
        except Exception:
            pass
        return False
    
    def get_stored_token(self):
        """获取存储的token"""
        token_file = PROJECT_DIR / ".token"
        if token_file.exists():
            return token_file.read_text().strip()
        return None
    
    def save_token(self, token):
        """保存token到本地"""
        token_file = PROJECT_DIR / ".token"
        token_file.write_text(token)
        # 设置权限，仅当前用户可读写
        os.chmod(token_file, 0o600)
    
    def clear_token(self):
        """清除token"""
        token_file = PROJECT_DIR / ".token"
        if token_file.exists():
            token_file.unlink()
    
    def get_initial_url(self):
        """获取初始加载URL"""
        if self.check_login_status():
            return f"{URL}/dashboard.html"
        return f"{URL}/login.html"
    
    def create_menu(self):
        """创建菜单栏"""
        menu_items = [
            {
                "label": "文件",
                "submenu": [
                    {"label": "刷新", "command": self.reload_page},
                    {"label": "首页", "command": self.go_home},
                    {"type": "separator"},
                    {"label": "退出", "command": self.quit_app}
                ]
            },
            {
                "label": "导航",
                "submenu": [
                    {"label": "客户管理", "command": lambda: self.navigate("/crm.html")},
                    {"label": "数据分析", "command": lambda: self.navigate("/analytics.html")},
                    {"label": "LinkedIn", "command": lambda: self.navigate("/linkedin.html")},
                    {"label": "AI配置", "command": lambda: self.navigate("/ai_config.html")},
                    {"label": "邮件管理", "command": lambda: self.navigate("/email.html")}
                ]
            },
            {
                "label": "帮助",
                "submenu": [
                    {"label": "关于", "command": self.show_about},
                    {"label": "检查更新", "command": self.check_update}
                ]
            }
        ]
        return menu_items
    
    def reload_page(self):
        """刷新页面"""
        if self.window:
            self.window.load_url(self.window.get_current_url())
    
    def go_home(self):
        """返回首页"""
        if self.window:
            self.window.load_url(f"{URL}/dashboard.html")
    
    def navigate(self, path):
        """导航到指定页面"""
        if self.window:
            self.window.load_url(f"{URL}{path}")
    
    def quit_app(self):
        """退出应用"""
        if self.window:
            self.window.destroy()
    
    def show_about(self):
        """显示关于对话框"""
        if self.window:
            self.window.evaluate_js("""
                alert('命运 (DESTINY) v1.0.0\\n\\n智能客户开发系统\\n\\n支持功能：\\n- 客户管理\\n- LinkedIn自动化\\n- AI内容生成\\n- 邮件营销\\n- 数据分析');
            """)
    
    def check_update(self):
        """检查更新"""
        if self.window:
            self.window.evaluate_js("""
                alert('当前版本: v1.0.0\\n\\n您已是最新版本！');
            """)
    
    def setup_js_api(self):
        """设置JS API，供前端调用"""
        class JSAPI:
            def __init__(self, app):
                self._app = app
            
            def save_token(self, token):
                """保存登录token"""
                self._app.save_token(token)
                self._app.is_logged_in = True
            
            def clear_token(self):
                """清除登录token"""
                self._app.clear_token()
                self._app.is_logged_in = False
            
            def get_version(self):
                """获取应用版本"""
                return "1.0.0"
            
            def get_user_info(self):
                """获取用户信息"""
                return json.dumps(self._app.current_user or {})
            
            def minimize_window(self):
                """最小化窗口"""
                if self._app.window:
                    self._app.window.minimize()
            
            def toggle_fullscreen(self):
                """切换全屏"""
                if self._app.window:
                    self._app.window.toggle_fullscreen()
        
        return JSAPI(self)
    
    def run(self):
        """运行应用"""
        logger.info("Starting %s", APP_TITLE)
        logger.info("Mode: %s, Directory: %s", "bundled" if IS_BUNDLED else "development", PROJECT_DIR)
        
        main_py = PROJECT_DIR / "backend" / "main.py"
        if not main_py.exists():
            show_error_dialog("启动错误", f"后端文件不存在:\n{main_py}")
            sys.exit(1)
        
        # 启动后台服务器
        logger.info("Starting server on %s:%s", HOST, PORT)
        self.server_thread = threading.Thread(target=self.start_server, daemon=True)
        self.server_thread.start()
        
        # 等待服务器就绪
        logger.info("Waiting for server...")
        if not self.wait_for_server(timeout=30):
            if self.server_error:
                error_msg = f"服务器启动失败:\n\n{self.server_error}"
            else:
                error_msg = "服务启动超时（30秒），请检查端口是否被占用。\n\n" \
                           f"地址: {URL}\n日志: {LOG_FILE}"
            show_error_dialog("启动错误", error_msg)
            sys.exit(1)
        
        logger.info("Server ready, opening window...")
        
        # 创建原生窗口（必须在主线程）
        try:
            import webview
            logger.info("pywebview version: %s", getattr(webview, '__version__', 'unknown'))
            
            js_api = self.setup_js_api()
            initial_url = self.get_initial_url()
            logger.info("Initial URL: %s", initial_url)
            
            window_kwargs = {
                "title": APP_TITLE,
                "url": initial_url,
                "width": 1400,
                "height": 900,
                "min_size": (1000, 700),
                "resizable": True,
                "confirm_close": True,
                "text_select": True,
                "js_api": js_api,
            }
            
            self.window = webview.create_window(**window_kwargs)
            logger.info("Window created, starting webview...")
            
            # webview.start() 会阻塞直到窗口关闭
            webview.start(debug=not IS_BUNDLED)
            
        except ImportError as e:
            logger.warning("pywebview import failed: %s, falling back to browser", e)
            show_error_dialog("组件缺失", f"pywebview 未安装，将使用浏览器打开。\n\n错误: {e}")
            self._open_in_browser()
        except Exception as e:
            logger.error("pywebview failed: %s\n%s", e, traceback.format_exc())
            show_error_dialog("窗口创建失败", f"无法创建原生窗口，将使用浏览器打开。\n\n错误: {e}")
            self._open_in_browser()
    
    def _open_in_browser(self):
        """回退到浏览器模式"""
        import webbrowser
        initial_url = self.get_initial_url()
        webbrowser.open(initial_url)
        logger.info("Opened in browser: %s", initial_url)


def main():
    # CRITICAL for PyInstaller on Windows — must be first thing
    import multiprocessing
    multiprocessing.freeze_support()
    
    try:
        logger.info("=== 命运 DESTINY 启动 ===")
        logger.info("Python: %s", sys.version)
        logger.info("Platform: %s", sys.platform)
        logger.info("PID: %s", os.getpid())
        logger.info("CWD: %s", os.getcwd())
        logger.info("Bundled: %s", IS_BUNDLED)
        logger.info("Log file: %s", LOG_FILE)
        
        app = DestinyApp()
        app.run()
    except Exception as e:
        error_msg = f"应用启动失败:\n\n{str(e)}\n\n{traceback.format_exc()}"
        logger.critical(error_msg)
        show_error_dialog("命运 - 启动错误", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Absolute last resort — write crash to desktop file
        import traceback as _tb
        _msg = f"命运 (DESTINY) 致命错误\n\n{e}\n\n{_tb.format_exc()}"
        try:
            if sys.platform == "win32":
                _desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
            else:
                _desktop = Path.home() / "Desktop"
            with open(_desktop / "Destiny-错误报告.txt", "w", encoding="utf-8") as f:
                f.write(_msg)
        except Exception:
            pass
        try:
            show_error_dialog("命运 - 致命错误", _msg)
        except Exception:
            pass
