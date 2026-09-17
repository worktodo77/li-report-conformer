# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LI Report Conformer — Windows .exe and macOS .app."""
import os
import sys
import glob
import PySide6
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# python-docx ships a default .docx template it needs at runtime; openpyxl + docx have lazily-imported
# submodules PyInstaller's static analysis misses. Collect them so the audit-log export works frozen.
_export_datas = collect_data_files('docx')
_export_hidden = (collect_submodules('docx') + collect_submodules('openpyxl')
                  + ['conformer.audit_export'])

# Qt platform plugins are REQUIRED for the app to start (without platforms/qwindows.dll Qt aborts with
# "no Qt platform plugin could be initialized"). The bundled qt.conf uses Prefix=., so Qt looks for
# them under PySide6/plugins/<group>/. Collect them explicitly — the auto-hook did not.
_qt_plugin_root = os.path.join(os.path.dirname(PySide6.__file__), 'plugins')
_qt_plugins = []
for _group in ('platforms', 'styles', 'imageformats', 'iconengines', 'tls', 'networkinformation'):
    for _dll in glob.glob(os.path.join(_qt_plugin_root, _group, '*.dll')):
        _qt_plugins.append((_dll, 'PySide6/plugins/' + _group))

a = Analysis(
    ['src/conformer/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/conformer/assets/template.dotx', 'conformer/assets'),
        ('src/conformer/assets/golden.docx', 'conformer/assets'),
        ('src/conformer/assets/KITCHEN_SINK.docx', 'conformer/assets'),
        ('src/conformer/assets/LI icon.png', 'conformer/assets'),
        ('src/conformer/assets/LI logo.png', 'conformer/assets'),
        ('src/conformer/ui/styles.qss', 'conformer/ui'),
    ] + _qt_plugins + _export_datas,
    hiddenimports=[
        'conformer',
        'conformer.engine',
        'conformer.scorer',
        'conformer.ui',
        'conformer.ui.window',
        'conformer.ui.preview',
        'conformer.ui.selftest',
        'conformer.audit_export',
    ] + _export_hidden,
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
    icon='src/conformer/assets/LI_icon.ico',
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
