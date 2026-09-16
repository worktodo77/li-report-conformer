# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LI Report Conformer — Windows .exe and macOS .app."""
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['src/conformer/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/conformer/assets/template.dotx', 'conformer/assets'),
        ('src/conformer/assets/golden.docx', 'conformer/assets'),
        ('src/conformer/assets/KITCHEN_SINK.docx', 'conformer/assets'),
        ('src/conformer/ui/styles.qss', 'conformer/ui'),
    ],
    hiddenimports=[
        'conformer',
        'conformer.engine',
        'conformer.scorer',
        'conformer.ui',
        'conformer.ui.window',
        'conformer.ui.preview',
        'conformer.ui.selftest',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy',
        'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtCharts',
        'PySide6.QtDataVisualization', 'PySide6.Qt3DCore',
        'PySide6.QtBluetooth', 'PySide6.QtMultimedia',
        'PySide6.QtPositioning', 'PySide6.QtSensors',
        'PySide6.QtSerialPort', 'PySide6.QtTest',
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
    name='LIReportConformer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LIReportConformer',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='LI Report Conformer.app',
        icon=None,
        bundle_identifier='com.longinternational.reportconformer',
        info_plist={
            'CFBundleName': 'LI Report Conformer',
            'CFBundleDisplayName': 'LI Report Conformer',
            'CFBundleVersion': '0.1.0',
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
        },
    )
