# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
web_dir = project_root / "src" / "ukrposhta_address_matcher" / "web"

a = Analysis(
    ["src/ukrposhta_address_matcher/windows_launcher.py"],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[(str(web_dir), "ukrposhta_address_matcher/web")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="UkrposhtaReviewUI",
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
