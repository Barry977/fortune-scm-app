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
    
    # Setup paths
    backend_dir = str(PROJECT_DIR / "backend")
    for p in [str(PROJECT_DIR), backend_dir]:
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(PROJECT_DIR)
    
    # Import and start the app
    try:
        print("\n📦 Loading application...")
        
        # Import the main module using importlib
        import importlib
        main_py = PROJECT_DIR / "backend" / "main.py"
        
        if not main_py.exists():
            print(f"❌ Not found: {main_py}")
            print(f"   Files: {list(PROJECT_DIR.iterdir())[:20]}")
            input("\nPress Enter to exit...")
            sys.exit(1)
        
        # Use runpy to run the module properly
        import runpy
        # We need to import the app object, not run the module
        # So use importlib instead
        spec = importlib.util.spec_from_file_location("main_app", str(main_py))
        mod = importlib.util.module_from_spec(spec)
        # Set __package__ so relative imports work
        mod.__package__ = "backend"
        spec.loader.exec_module(mod)
        app = mod.app
        
        print("✅ Application loaded")
        
    except Exception as e:
        print(f"\n❌ Failed to load: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Start server
    try:
        print(f"\n🌐 Server starting at {URL}")
        print("   Browser will open automatically...")
        print("   Press Ctrl+C to stop\n")
        
        def open_browser():
            time.sleep(3)
            webbrowser.open(URL)
        threading.Thread(target=open_browser, daemon=True).start()
        
        import uvicorn
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
        
    except KeyboardInterrupt:
        print("\n\n👋 Stopped.")
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            print(f"\n⚠️  Port {PORT} already in use, opening browser...")
            webbrowser.open(URL)
            input("\nPress Enter to exit...")
        else:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to exit...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
