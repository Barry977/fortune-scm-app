#!/usr/bin/env python3
"""
Build script for Fortune SCM Desktop App
Packages the app as a standalone desktop application using PyInstaller.
"""

import os
import sys
import shutil
import subprocess
import platform

def clean_build():
    """Clean previous build artifacts."""
    dirs_to_clean = ['build', 'dist']
    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"Cleaning {d}...")
            shutil.rmtree(d)

def install_dependencies():
    """Install required dependencies."""
    print("Installing dependencies...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)

def build_app():
    """Build the application using PyInstaller."""
    print("Building application...")
    
    # Run PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        'fortune_scm.spec',
        '--clean',
        '--noconfirm',
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Build failed!")
        print(result.stderr)
        sys.exit(1)
    
    print(result.stdout)

def create_data_dir():
    """Ensure data directory exists in the dist."""
    app_name = 'Destiny' if platform.system() == 'Windows' else '命运'
    dist_path = os.path.join('dist', app_name)
    if platform.system() == 'Darwin':
        # macOS .app bundle
        dist_path = os.path.join('dist', '命运.app', 'Contents', 'MacOS')
    
    data_dir = os.path.join(dist_path, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Copy existing database if present
    if os.path.exists('data/fortune.db'):
        shutil.copy2('data/fortune.db', data_dir)
        print(f"Copied database to {data_dir}")

def create_installer():
    """Create installer package based on platform."""
    system = platform.system()
    
    if system == 'Darwin':
        create_macos_dmg()
    elif system == 'Windows':
        create_windows_installer()
    else:
        print(f"No installer creation for {system}")

def create_macos_dmg():
    """Create macOS DMG installer."""
    print("Creating macOS DMG...")
    
    dmg_name = 'Destiny-Installer.dmg'
    app_path = os.path.join('dist', '命运.app')
    
    if not os.path.exists(app_path):
        print(f"App not found at {app_path}")
        return
    
    # Create DMG using hdiutil
    cmd = [
        'hdiutil', 'create',
        '-volname', '命运 (DESTINY)',
        '-srcfolder', app_path,
        '-ov', '-format', 'UDZO',
        os.path.join('dist', dmg_name)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Created DMG: dist/{dmg_name}")
    except FileNotFoundError:
        print("hdiutil not found, skipping DMG creation")

def create_windows_installer():
    """Create Windows installer (requires NSIS)."""
    print("Windows installer creation requires NSIS")
    print("Please install NSIS and create installer manually")

def print_summary():
    """Print build summary."""
    system = platform.system()
    app_name = 'Destiny' if system == 'Windows' else '命运'
    
    print("\n" + "=" * 60)
    print("BUILD COMPLETE!")
    print("=" * 60)
    
    if system == 'Darwin':
        print("\nmacOS Application:")
        print(f"  - App Bundle: dist/{app_name}.app")
        print(f"  - DMG Installer: dist/Destiny-Installer.dmg")
        print("\nTo distribute:")
        print("  1. Share the .app bundle (drag to Applications)")
        print("  2. Or share the .dmg file")
    elif system == 'Windows':
        print("\nWindows Application:")
        print(f"  - Executable: dist/{app_name}/{app_name}.exe")
        print("\nTo distribute:")
        print(f"  1. Zip the 'dist/{app_name}' folder")
        print("  2. Share the zip file")
    else:
        print(f"\nLinux Application:")
        print(f"  - Executable: dist/{app_name}/{app_name}")
    
    print("\n" + "=" * 60)

def main():
    """Main build process."""
    print("Fortune SCM Desktop App Builder")
    print("=" * 60)
    
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Build steps
    clean_build()
    install_dependencies()
    build_app()
    create_data_dir()
    create_installer()
    print_summary()

if __name__ == '__main__':
    main()
