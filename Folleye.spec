# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('image', 'image'),
        ('resources', 'resources'),
    ],
    hiddenimports=[
        'objc', 'Cocoa', 'AppKit', 'Foundation', 'Quartz',
        'cv2', 'mediapipe', 'numpy',
        'app.menubar', 'app.onboarding', 'app.overlay',
        'app.gaze_engine', 'app.calibration', 'app.windows', 'app.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'scipy', 'pandas', 'matplotlib', 'sympy',
        'sklearn', 'skimage',
        'IPython', 'jupyter', 'notebook',
        'tensorflow', 'keras',
        'PyQt5', 'PyQt6', 'wx', 'tkinter',
        'jinja2', 'flask', 'django',
        'fsspec', 'pyarrow', 'sqlalchemy',
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
    name='Folleye',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Folleye',
)

app = BUNDLE(
    coll,
    name='Folleye.app',
    bundle_identifier='com.kanryul225.folleye',
    version='1.0.0',
    info_plist={
        'NSCameraUsageDescription': 'Folleye uses your camera to detect eye gaze for scroll routing.',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,
        'CFBundleShortVersionString': '1.0.0',
    },
)
