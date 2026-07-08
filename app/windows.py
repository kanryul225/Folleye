import Quartz
from Quartz import CGWarpMouseCursorPosition, CGEventCreate, CGEventGetLocation


def list_windows():
    """화면에 떠 있는 일반 창 목록과 bounding box를 반환."""
    options = (
        Quartz.kCGWindowListOptionOnScreenOnly
        | Quartz.kCGWindowListExcludeDesktopElements
    )
    info_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    windows = []
    for info in info_list:
        if info.get("kCGWindowLayer", 0) != 0:
            continue
        bounds = info.get("kCGWindowBounds", {})
        if not bounds.get("Width") or not bounds.get("Height"):
            continue
        windows.append({
            "owner": info.get("kCGWindowOwnerName", ""),
            "name":  info.get("kCGWindowName", ""),
            "x":     bounds["X"],
            "y":     bounds["Y"],
            "width": bounds["Width"],
            "height": bounds["Height"],
        })
    return windows


def window_at(point, windows):
    """주어진 좌표가 속한 창을 반환. 없으면 None."""
    x, y = point
    for w in windows:
        if w["x"] <= x <= w["x"] + w["width"] and w["y"] <= y <= w["y"] + w["height"]:
            return w
    return None


def window_key(w):
    return (w["owner"], w["name"], w["x"], w["y"])


def get_cursor_pos():
    loc = CGEventGetLocation(CGEventCreate(None))
    return loc.x, loc.y


def move_cursor(x, y):
    CGWarpMouseCursorPosition((x, y))
