# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LI Report Conformer — Windows .exe and macOS .app."""
import os
import sys
import glob
import PySide6
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# --- build stamp: bake the git commit (and UTC build time) into a data file so every build, and every
# conformed document's audit, self-identifies. No more guessing which commit an .exe/.app came from. ---
import subprocess as _sp
import tempfile as _tf
import datetime as _dt
def _write_build_stamp():
    try:
        _sha = _sp.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
        _dirty = _sp.check_output(['git', 'status', '--porcelain']).decode().strip()
        _sha += '-dirty' if _dirty else ''
    except Exception:
        _sha = 'unknown'
    _dir = _tf.mkdtemp(prefix='li_build_stamp_')
    _p = os.path.join(_dir, 'BUILD_STAMP.txt')
    with open(_p, 'w', encoding='utf-8') as _f:
        _f.write(f"{_sha}  built {_dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    return _p
_BUILD_STAMP = _write_build_stamp()

# python-docx ships a default .docx template it needs at runtime; openpyxl + docx have lazily-imported
# submodules PyInstaller's static analysis misses. Collect them so the audit-log export works frozen.
_export_datas = collect_data_files('docx')
_export_hidden = (collect_submodules('docx') + collect_submodules('openpyxl')
                  + ['conformer.audit_export'])

# Qt platform plugins are REQUIRED for the app to start (without platforms/qwindows.dll Qt aborts with
# "no Qt platform plugin could be initialized"). The bundled qt.conf uses Prefix=., so Qt looks for
# them under PySide6/plugins/<group>/. Collect them explicitly — the auto-hook did not.
_qt_plugin_root = os.path.join(os.path.dirname(PySide6.__file__), 'plugins')
# Qt plugin shared-library extension is platform specific: .dll on Windows, .dylib on macOS, .so on Linux.
# Globbing only *.dll silently bundled NO plugins on macOS -> the .app aborted with "no Qt platform plugin".
_qt_plugin_ext = {'win32': '*.dll', 'darwin': '*.dylib'}.get(sys.platform, '*.so')
_qt_plugins = []
for _group in ('platforms', 'styles', 'imageformats', 'iconengines', 'tls', 'networkinformation'):
    for _lib in glob.glob(os.path.join(_qt_plugin_root, _group, _qt_plugin_ext)):
        _qt_plugins.append((_lib, 'PySide6/plugins/' + _group))

a = Analysis(
    ['src/conformer/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/conformer/assets/template.dotx', 'conformer/assets'),   # LI Letter (LTR) July 2026 template
        ('src/conformer/assets/LI Report Template A4 23 July 2026.dotx', 'conformer/assets'),  # A4 variant (F7)
        ('src/conformer/assets/golden.docx', 'conformer/assets'),
        ('src/conformer/assets/KITCHEN_SINK.docx', 'conformer/assets'),
        ('src/conformer/assets/LI icon.png', 'conformer/assets'),
        ('src/conformer/assets/LI logo.png', 'conformer/assets'),
        ('src/conformer/ui/styles.qss', 'conformer/ui'),
        (_BUILD_STAMP, 'conformer/assets'),                           # git SHA + build time (build stamp)
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
        'conformer.numbering',
        'conformer.tablespec',
        'conformer.buildinfo',
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
    icon=('src/conformer/assets/LI_icon.ico' if sys.platform == 'win32' else None),
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
