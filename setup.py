from setuptools import setup

APP = ['main.py']
OPTIONS = {
    'argv_emulation': False,
    'packages': ['cv2', 'mediapipe', 'numpy', 'objc', 'Cocoa', 'app'],
    'resources': ['image', 'resources'],
    'plist': {
        'CFBundleName': 'Folleye',
        'CFBundleDisplayName': 'Folleye',
        'CFBundleIdentifier': 'com.kanryul225.folleye',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSCameraUsageDescription': 'Folleye uses your camera to detect eye gaze for scroll routing.',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,
    },
}

setup(
    name='Folleye',
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
