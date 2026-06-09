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
from pathlib import Path

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


class DestinyApp:
    """桌面应用主类"""
    
    def __init__(self):
        self.window = None
        self.server_thread = None
        self.is_logged_in = False
        self.current_user = None
    
    def start_server(self):
        """在后台线程启动 FastAPI 服务器。"""
        backend_dir = PROJECT_DIR / "backend"
        for p in [str(backend_dir), str(PROJECT_DIR)]:
            if p not in sys.path:
                sys.path.insert(0, p)
        os.chdir(PROJECT_DIR)
        
        import uvicorn
        uvicorn.run("main:app", host=HOST, port=PORT, log_level="warning", access_log=False)
    
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
                self.app = app
            
            def save_token(self, token):
                """保存登录token"""
                self.app.save_token(token)
                self.app.is_logged_in = True
            
            def clear_token(self):
                """清除登录token"""
                self.app.clear_token()
                self.app.is_logged_in = False
            
            def get_version(self):
                """获取应用版本"""
                return "1.0.0"
            
            def get_user_info(self):
                """获取用户信息"""
                return json.dumps(self.app.current_user or {})
            
            def minimize_window(self):
                """最小化窗口"""
                if self.app.window:
                    self.app.window.minimize()
            
            def toggle_fullscreen(self):
                """切换全屏"""
                if self.app.window:
                    self.app.window.toggle_fullscreen()
        
        return JSAPI(self)
    
    def run(self):
        """运行应用"""
        print("=" * 50)
        print(f"  🔧 {APP_TITLE}")
        print("=" * 50)
        
        mode = "bundled" if IS_BUNDLED else "development"
        print(f"📦 Mode: {mode}")
        print(f"📂 Directory: {PROJECT_DIR}")
        
        main_py = PROJECT_DIR / "backend" / "main.py"
        if not main_py.exists():
            print(f"❌ 后端文件不存在: {main_py}")
            if getattr(sys.stdin, 'isatty', lambda: False)():
                input("\n按回车键退出...")
            sys.exit(1)
        
        # 启动后台服务器
        print("🚀 正在启动服务...")
        self.server_thread = threading.Thread(target=self.start_server, daemon=True)
        self.server_thread.start()
        
        # 等待服务器就绪
        print("⏳ 等待服务就绪...")
        if not self.wait_for_server(timeout=30):
            print("❌ 服务启动超时")
            if getattr(sys.stdin, 'isatty', lambda: False)():
                input("\n按回车键退出...")
            sys.exit(1)
        
        print("✅ 服务已就绪")
        print(f"🖥️ 正在打开应用窗口...\n")
        
        # 创建原生窗口（必须在主线程）
        try:
            import webview
            
            # 创建JS API
            js_api = self.setup_js_api()
            
            # 确定初始URL
            initial_url = self.get_initial_url()
            
            # 创建窗口
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
            
            # 添加图标（如果存在）
            # Note: pywebview 不支持 icon 参数，图标通过 .app bundle 或 .ico 设置
            # if APP_ICON and os.path.exists(APP_ICON):
            #     window_kwargs["icon"] = APP_ICON
            
            self.window = webview.create_window(**window_kwargs)
            
            # 设置菜单（macOS/Linux支持）
            if hasattr(webview, 'menu'):
                try:
                    webview.menu = self.create_menu()
                except Exception:
                    pass
            
            # webview.start() 会阻塞直到窗口关闭
            webview.start(debug=not IS_BUNDLED)
            
        except ImportError:
            print("⚠️ pywebview 未安装，回退到浏览器模式...")
            import webbrowser
            webbrowser.open(self.get_initial_url())
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
            if getattr(sys.stdin, 'isatty', lambda: False)():
                input("\n按回车键退出...")
            sys.exit(1)
        
        print("\n👋 应用已关闭")


def main():
    app = DestinyApp()
    app.run()


if __name__ == "__main__":
    main()
