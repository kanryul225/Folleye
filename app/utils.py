import sys
import pathlib


def resource_path(filename: str) -> pathlib.Path:
    """개발 환경과 .app 번들 양쪽에서 리소스 파일 경로를 반환."""
    if getattr(sys, "frozen", False):
        # py2app으로 패키징된 .app 번들 안
        return pathlib.Path(sys.executable).parent.parent / "Resources" / filename
    else:
        # 개발 환경 (소스에서 직접 실행)
        return pathlib.Path(__file__).parent.parent / "resources" / filename
