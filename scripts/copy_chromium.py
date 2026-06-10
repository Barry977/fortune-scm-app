"""Copy Playwright's bundled Chromium to data/chromium for PyInstaller packaging."""
import os
import shutil
import platform
from pathlib import Path


def copy_chromium():
    if platform.system() == "Windows":
        src = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    else:
        src = Path.home() / "Library" / "Caches" / "ms-playwright"

    dst = Path("data/chromium")

    if not src.exists():
        print(f"Warning: ms-playwright not found at {src}")
        return False

    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    print(f"Chromium copied from {src} to {dst}")

    # Print contents for CI debugging
    total_size = 0
    for p in dst.rglob("*"):
        if p.is_file():
            total_size += p.stat().st_size
    print(f"Total size: {total_size / 1024 / 1024:.1f} MB")
    for p in sorted(dst.iterdir()):
        print(f"  {p.name}/")
    return True


if __name__ == "__main__":
    copy_chromium()
