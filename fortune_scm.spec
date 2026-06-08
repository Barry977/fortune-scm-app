# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Fortune SCM Desktop App
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all frontend templates and static files
datas = [
    ('frontend', 'frontend'),
    ('data', 'data'),
]

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
    'passlib',
    'bcrypt',
    'sqlite3',
    'webview',
    'apscheduler',
    'httpx',
    'playwright',
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
]

a = Analysis(
    ['start.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Fortune SCM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/static/icon.ico' if os.path.exists('frontend/static/icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Fortune SCM',
)

# For macOS .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Fortune SCM.app',
        icon='frontend/static/icon.ico' if os.path.exists('frontend/static/icon.ico') else None,
        bundle_identifier='com.fortunescm.app',
        info_plist={
            'CFBundleName': 'Fortune SCM',
            'CFBundleDisplayName': 'Fortune SCM',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
        },
    )
