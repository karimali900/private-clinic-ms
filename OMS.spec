# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Obstetrics Management System
# Created by Karim Abdelaziz — 00201029927276

import sys
from pathlib import Path

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data')],
    hiddenimports=['passlib.handlers.pbkdf2_sha256', 'passlib.handlers.sha2_crypt', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.middleware.asgi2', 'uvicorn.middleware.wsgi', 'uvicorn.lifespan.on', 'fastapi', 'pydantic', 'starlette.middleware.cors', 'websockets', 'websockets.legacy.client', 'websockets.legacy.server', 'httptools', 'database', 'multipart', 'multipart.multipart'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'matplotlib', 'scipy', 'numpy', 'pandas', 'PIL', 'cv2', 'cryptography', 'email', 'unittest', 'test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OMS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if Path('icon.ico').exists() else None,
)
