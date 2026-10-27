# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

spec_dir = Path(SPECPATH).resolve()
root = spec_dir.parent
assets = root / "Assets"
win = spec_dir

a = Analysis(
    [str(win / "leiyu_pet.py")],
    pathex=[str(win), str(root)],
    binaries=[],
    datas=[
        (str(win / "lei.png"), "Assets"),
        (str(win / "yu.png"), "Assets"),
        (str(assets / "clips.json"), "Assets"),
        (str(assets / "clips-helium.json"), "Assets"),
        (str(assets / "pairs.json"), "Assets"),
        (str(assets / "Clips"), "Assets/Clips"),
        (str(assets / "Clips-helium"), "Assets/Clips-helium"),
    ],
    hiddenimports=["pygame"],
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
    name="LeiYuDesktopPets",
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
