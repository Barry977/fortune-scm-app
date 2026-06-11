# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for 命运 (DESTINY) Desktop App
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Get the project directory
PROJECT_DIR = Path('.').resolve()

# Collect all frontend templates, static files, AND backend code
# Only include directories that exist (CI may not have data/ etc.)
datas = []
for src, dst in [
    ('frontend', 'frontend'),
    ('data', 'data'),
    ('backend', 'backend'),
    ('templates', 'templates'),
]:
    p = PROJECT_DIR / src
    if p.exists():
        datas.append((str(p), dst))

# Collect bcrypt's native extension
from PyInstaller.utils.hooks import collect_all as _collect_all
_bd, _bi, _hi = _collect_all('bcrypt')
datas += _bd
binaries_extra = _bi
hiddenimports_extra = _hi

# Collect playwright (includes Chromium browser binaries)
_pd, _pi, _ph = _collect_all('playwright')
datas += _pd
binaries_extra += _pi
hiddenimports_extra += _ph

# Include Playwright's downloaded Chromium browser
import glob as _glob
_pw_browser_dirs = []
if sys.platform == 'win32':
    _candidates = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright'),
        os.path.join(os.path.expanduser('~'), '.cache', 'ms-playwright'),
    ]
else:
    _candidates = [
        os.path.join(os.path.expanduser('~'), 'Library', 'Caches', 'ms-playwright'),
        os.path.join(os.path.expanduser('~'), '.cache', 'ms-playwright'),
    ]
for _cand in _candidates:
    if os.path.isdir(_cand):
        _pw_browser_dirs.append(_cand)
        break

if _pw_browser_dirs:
    for _pw_dir in _pw_browser_dirs:
        # Add each subdirectory (chromium-xxx, ffmpeg-xxx, etc.)
        for _entry in os.listdir(_pw_dir):
            _entry_path = os.path.join(_pw_dir, _entry)
            if os.path.isdir(_entry_path):
                datas.append((_entry_path, os.path.join('playwright-browsers', _entry)))
                print(f"  Including: {_entry}")
        break
else:
    print("WARNING: Playwright browser directory not found! LinkedIn features may not work.")

# Add hidden imports for backend modules
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'jose',
    'python_jose',
    'python_jose.cryptography_backend',
    'cryptography',
    'passlib',
    'bcrypt',
    'sqlite3',
    'webview',
    'apscheduler',
    'httpx',
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'backend.main',
    'backend.auth',
    'backend.database',
    'backend.linkedin_service',
    'backend.linkedin_routes',
    'backend.ai_content',
    'backend.ai_content_routes',
    'backend.auto_import',
    'backend.auto_import_routes',
    'backend.import_export',
    'backend.import_export_routes',
    'backend.linkedin_analytics',
    'backend.linkedin_analytics_routes',
    'backend.linkedin_scheduler',
    'backend.scheduler',
    'backend.scheduler_routes',
    'backend.crm',
    'backend.crm_routes',
    'backend.email_smtp',
    'backend.email_routes',
    'backend.materials',
    'backend.materials_routes',
    'backend.ai_config',
    'backend.ai_config_routes',
    'backend.analytics',
    'backend.analytics_routes',
    'backend.schemas',
    'backend.ai_config_schemas',
    'backend.crm_schemas',
    'backend.email_schemas',
    'backend.linkedin_schemas',
    'playwright',
    'playwright.async_api',
    'playwright.sync_api',
]

a = Analysis(
    ['start.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=binaries_extra,
    datas=datas,
    hiddenimports=hiddenimports + hiddenimports_extra,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use English name on Windows to avoid encoding issues
import platform as _plat
_app_name = 'Destiny' if _plat.system() == 'Windows' else '命运'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=_app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/assets/icon.ico' if os.path.exists('frontend/assets/icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=_app_name,
)

# For macOS .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='命运.app',
        icon='frontend/assets/icon.icns' if os.path.exists('frontend/assets/icon.icns') else None,
        bundle_identifier='com.destiny.app',
        info_plist={
            'CFBundleName': '命运',
            'CFBundleDisplayName': '命运 (DESTINY)',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
        },
    )
