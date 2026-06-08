#!/usr/bin/env python3
"""
Fortune SCM App - Launcher
"""

import os
import sys
import time
import webbrowser
import threading
from pathlib import Path

IS_BUNDLED = getattr(sys, '_MEIPASS', None) is not None

if IS_BUNDLED:
    PROJECT_DIR = Path(sys._MEIPASS)
else:
    PROJECT_DIR = Path(__file__).parent.resolve()

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def main():
    print("=" * 50)
    print("  🔧 Fortune SCM App")
    print("=" * 50)
    
    mode = "bundled" if IS_BUNDLED else "development"
    print(f"📦 Mode: {mode}")
    print(f"📂 Directory: {PROJECT_DIR}")
    
    backend_dir = PROJECT_DIR / "backend"
    main_py = backend_dir / "main.py"
    
    if not main_py.exists():
        print(f"\n❌ backend/main.py not found!")
        print(f"   Expected: {main_py}")
        print(f"   Available: {list(PROJECT_DIR.iterdir())[:20]}")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Setup Python paths - backend dir first so 'import main' finds backend/main.py
    for p in [str(backend_dir), str(PROJECT_DIR)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    
    # Change to project dir so backend/main.py can find frontend/ via relative paths
    os.chdir(PROJECT_DIR)
    
    print(f"\n🌐 Starting server at {URL}")
    print("   Browser will open automatically...")
    print("   Press Ctrl+C to stop\n")
    
    # Open browser
    def open_browser():
        time.sleep(3)
        webbrowser.open(URL)
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run uvicorn
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host=HOST,
            port=PORT,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n👋 Stopped.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
