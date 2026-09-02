# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 目录型桌面发行包。"""

import sys
from pathlib import Path


ROOT = Path(SPECPATH)
APP_NAME = "InteractiveVisionTraining"

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "test_images"), "test_images"),
    (str(ROOT / "training_images"), "training_images"),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "EXPERIMENT_CHECKLIST.md"), "."),
    (str(ROOT / "TEST2_3_CHECKLIST.md"), "."),
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        collection,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier="edu.opencv-course.interactive-vision-training",
        info_plist={
            "CFBundleDisplayName": "OpenCV Interactive Training",
            "CFBundleName": APP_NAME,
            "NSHighResolutionCapable": True,
        },
    )
