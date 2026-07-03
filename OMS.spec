# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data')],
    hiddenimports=['passlib.handlers.pbkdf2_sha256', 'passlib.handlers.sha2_crypt', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.middleware.asgi2', 'uvicorn.middleware.wsgi', 'uvicorn.lifespan.on', 'fastapi', 'pydantic', 'starlette.middleware.cors', 'websockets', 'websockets.legacy.client', 'websockets.legacy.server', 'httptools', 'database', 'multipart', 'multipart.multipart', 'sklearn', 'sklearn.ensemble', 'sklearn.tree', 'sklearn.preprocessing', 'pandas', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
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
)
