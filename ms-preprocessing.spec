# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for MS Preprocessing Toolkit.

Build command:
    pyinstaller ms-preprocessing.spec --clean --noconfirm

Requirements:
    - ms-core submodule must be checked out: git submodule update --init --recursive
    - Run from the ms-preprocessing-toolkit root directory
"""
import sys
from pathlib import Path
import customtkinter
from PyInstaller.building.osx import BUNDLE

block_cipher = None

# ms-core submodule src — lets PyInstaller discover ms_core.* during static analysis
ms_core_src = str(Path("ms-core/src").resolve())
builtin_profiles_dir = str(Path("src/ms_preprocessing/resources/builtin_profiles").resolve())

a = Analysis(
    ["src/ms_preprocessing/main.py"],
    pathex=[ms_core_src],
    binaries=[],
    datas=[
        # customtkinter themes and assets must be bundled
        (customtkinter.__path__[0], "customtkinter/"),
        # built-in YAML profiles are loaded through importlib.resources
        (builtin_profiles_dir, "ms_preprocessing/resources/builtin_profiles"),
    ],
    hiddenimports=[
        "customtkinter",
        "PIL._tkinter_finder",
        "openpyxl.cell._writer",
        "ms_core.preprocessing.data_organizer",
        "ms_core.preprocessing.istd_marker",
        "ms_core.preprocessing.duplicate_remover",
        "ms_core.preprocessing.ms_quality_filter",
        "ms_core.utils.file_handler",
        "ms_core.preprocessing.settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "sklearn",
        "statsmodels",
        "seaborn",
        "plotly",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ms-preprocessing",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # windowed mode: no console window for GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="ms-preprocessing.app",
        icon=None,
        bundle_identifier="com.ms.preprocessing.toolkit",
    )
