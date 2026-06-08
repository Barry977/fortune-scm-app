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

# Detect if running as PyInstaller bundle
IS_BUNDLED = getattr(sys, '_MEIPASS', None) is not None

if IS_BUNDLED:
    # PyInstaller extracts data files to _MEIPASS temp dir
    PROJECT_DIR = Path(sys._MEIPASS)
else:
    PROJECT_DIR = Path(__file__).parent.resolve()

VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def get_python():
    """Get the Python interpreter."""
    if IS_BUNDLED:
        return sys.executable
    
    venv_python = VENV_DIR / "bin" / "python"
    if sys.platform == "win32":
        venv_python = VENV_DIR / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def create_venv():
    """Create virtual environment if needed (only for non-bundled)."""
    if IS_BUNDLED:
        return
    
    if VENV_DIR.exists():
        return
    print("📦 Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    print("✅ Virtual environment created.")


def install_deps():
    """Install dependencies (only for non-bundled)."""
    if IS_BUNDLED:
        return
    
    python = get_python()
    marker = PROJECT_DIR / ".deps_installed"
    req_mtime = REQUIREMENTS.stat().st_mtime if REQUIREMENTS.exists() else 0
    if marker.exists() and marker.stat().st_mtime >= req_mtime:
        print("✅ Dependencies already installed.")
        return

    print("📦 Installing dependencies...")
    subprocess.run([python, "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True)
    subprocess.run([python, "-m", "pip", "install", "-r", str(REQUIREMENTS)], check=True)
    marker.touch()
    print("✅ Dependencies installed.")


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
    for f in PROJECT_DIR.glob("*.py"):
        text = f.read_text()
        if "FastAPI" in text and "app" in text:
            return f
    return None


def main():
    os.chdir(PROJECT_DIR)
    print("=" * 50)
    print("  🔧 Fortune SCM App")
    print("=" * 50)

    if IS_BUNDLED:
        print(f"📦 Running as bundled application")
        print(f"   Data dir: {PROJECT_DIR}")
        
        main_module = find_main_module()
        
        if main_module:
            backend_dir = main_module.parent
            env = os.environ.copy()
            env["PYTHONPATH"] = str(PROJECT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
            
            print(f"\n🌐 Starting server at {URL}")
            print("   Press Ctrl+C to stop\n")
            
            # Open browser
            import threading
            def open_browser():
                time.sleep(3)
                webbrowser.open(URL)
            threading.Thread(target=open_browser, daemon=True).start()
            
            # Run uvicorn directly (no subprocess, since we're in the bundle)
            try:
                import uvicorn
                # Import the app
                sys.path.insert(0, str(backend_dir))
                uvicorn.run("main:app", host=HOST, port=PORT, log_level="info")
            except KeyboardInterrupt:
                print("\n👋 Shutting down...")
                sys.exit(0)
        else:
            print("❌ No main module found!")
            print(f"   Looked in: {PROJECT_DIR}")
            print(f"   Contents: {list(PROJECT_DIR.iterdir())[:20]}")
            input("Press Enter to exit...")
            sys.exit(1)
    else:
        # Normal development mode
        create_venv()
        install_deps()
        
        python = get_python()
        main_module = find_main_module()
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        
        if main_module:
            backend_dir = main_module.parent
            cmd = [python, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT), "--reload"]
            run_cwd = str(backend_dir)
        else:
            print("⚠️  No main module found.")
            sys.exit(1)
        
        print(f"\n🌐 Starting server at {URL}")
        print("   Press Ctrl+C to stop\n")
        
        import threading
        def open_browser():
            time.sleep(2)
            webbrowser.open(URL)
        threading.Thread(target=open_browser, daemon=True).start()
        
        try:
            subprocess.run(cmd, cwd=run_cwd, env=env)
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
            sys.exit(0)


if __name__ == "__main__":
    main()
