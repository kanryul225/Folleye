import sys
import pathlib


def resource_path(filename: str) -> pathlib.Path:
    """개발 환경과 .app 번들 양쪽에서 리소스 파일 경로를 반환."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller 번들
        return pathlib.Path(sys._MEIPASS) / "resources" / filename
    else:
        # 개발 환경
        return pathlib.Path(__file__).parent.parent / "resources" / filename
