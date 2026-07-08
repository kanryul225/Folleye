"""
1단계: 화면에 떠 있는 창들의 위치/크기(bounding box)를 가져온다.
나중에 시선 좌표가 이 박스들 중 어디에 속하는지 판정하는 데 쓸 정보.

사용법:
    python list_windows.py
"""

import Quartz

OPTIONS = (
    Quartz.kCGWindowListOptionOnScreenOnly
    | Quartz.kCGWindowListExcludeDesktopElements
)


def list_windows():
    info_list = Quartz.CGWindowListCopyWindowInfo(OPTIONS, Quartz.kCGNullWindowID)
    windows = []
    for info in info_list:
        layer = info.get("kCGWindowLayer", 0)
        if layer != 0:
            # layer 0이 아닌 건 메뉴바, Dock, 알림창 같은 시스템 UI라서 제외
            continue

        bounds = info.get("kCGWindowBounds", {})
        if not bounds.get("Width") or not bounds.get("Height"):
            continue

        windows.append({
            "owner": info.get("kCGWindowOwnerName", ""),
            "name": info.get("kCGWindowName", ""),
            "x": bounds["X"],
            "y": bounds["Y"],
            "width": bounds["Width"],
            "height": bounds["Height"],
        })
    return windows


if __name__ == "__main__":
    for w in list_windows():
        print(
            f"owner={w['owner']!r:25} name={w['name']!r:25} "
            f"x={w['x']:.0f} y={w['y']:.0f} w={w['width']:.0f} h={w['height']:.0f}"
        )
