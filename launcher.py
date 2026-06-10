#!/usr/bin/env python3
"""
Destiny Launcher - Minimal startup diagnostics
This runs BEFORE anything else to catch early crashes.
"""

import sys
import os
import ctypes
import traceback

def msg(title, text):
    """Show a Windows message box."""
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except Exception:
        print(f"\n=== {title} ===\n{text}\n")

def main():
    # Step 1: Basic sanity
    try:
        msg("启动检测", f"Python {sys.version}\n平台: {sys.platform}\n路径: {sys.executable}")
    except Exception as e:
        # Can't even show a message box - write to file
        with open(os.path.expanduser("~/destiny-crash.txt"), "w") as f:
            f.write(f"Cannot show message box: {e}\n{traceback.format_exc()}")
        return

    # Step 2: Check if we're bundled
    is_bundled = getattr(sys, '_MEIPASS', None) is not None
    if is_bundled:
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    # Step 3: Check critical files
    checks = []
    for f in ["backend/main.py", "frontend/templates/login.html"]:
        path = os.path.join(base, f)
        exists = os.path.exists(path)
        checks.append(f"{'✅' if exists else '❌'} {f}")

    msg("文件检查", "\n".join(checks))

    # Step 4: Try importing pywebview
    try:
        import webview
        msg("pywebview", f"✅ 版本: {getattr(webview, '__version__', 'unknown')}")
    except ImportError as e:
        msg("pywebview 缺失", f"❌ {e}\n\n需要安装: pip install pywebview")
        return
    except Exception as e:
        msg("pywebview 错误", f"❌ {e}")
        return

    # Step 5: Try importing uvicorn
    try:
        import uvicorn
        msg("uvicorn", "✅ 已安装")
    except ImportError as e:
        msg("uvicorn 缺失", f"❌ {e}")
        return

    # Step 6: All checks passed, launch the real app
    msg("检测通过", "所有组件正常，正在启动应用...")

    # Import and run the actual app
    try:
        from start import DestinyApp
        app = DestinyApp()
        app.run()
    except Exception as e:
        msg("应用启动失败", f"{e}\n\n{traceback.format_exc()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        msg("致命错误", f"{e}\n\n{traceback.format_exc()}")
