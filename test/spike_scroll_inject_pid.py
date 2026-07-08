"""
0단계 스파이크 (2차): 좌표 기반이 아니라 PID(프로세스)를 직접 지정해서
스크롤 이벤트를 보낸다. 이러면 커서 위치/z-order와 무관하게
특정 앱에만 스크롤이 가야 한다.

사용법:
1. 타겟 앱(예: "Claude", "GoodNotes", "ChatGPT") 실행
2. python spike_scroll_inject_pid.py
3. 실행 중인 앱 이름 목록이 출력되면, 정확한 이름을 입력
4. 마우스를 다른 곳에 두고 엔터 -> 스크롤 이벤트가 그 앱으로 전송됨
5. 커서가 그대로 있는지, 다른 창에 가려진 상태에서도 스크롤되는지 확인
"""

import Quartz
from AppKit import NSWorkspace


def find_pid_by_name(app_name):
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    matches = [a for a in apps if app_name.lower() in (a.localizedName() or "").lower()]
    if not matches:
        return None
    return matches[0].processIdentifier()


def list_running_apps():
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    names = sorted(set(a.localizedName() for a in apps if a.localizedName()))
    print("실행 중인 앱 목록:")
    for n in names:
        print(f"  - {n}")


def inject_scroll_to_pid(pid, amount):
    event = Quartz.CGEventCreateScrollWheelEvent(
        None,
        Quartz.kCGScrollEventUnitPixel,
        1,
        amount,
    )
    Quartz.CGEventPostToPid(pid, event)


if __name__ == "__main__":
    list_running_apps()
    target_name = input("\n타겟 앱 이름 입력: ").strip()
    pid = find_pid_by_name(target_name)
    if pid is None:
        print("해당 이름의 앱을 찾지 못했습니다.")
    else:
        print(f"'{target_name}' PID = {pid}")
        input("마우스를 다른 곳(또는 다른 창)에 두고 엔터를 누르면 스크롤 이벤트를 보냅니다...")
        inject_scroll_to_pid(pid, -200)
        print("전송 완료. 커서가 그대로인지, 가려진 상태에서도 스크롤됐는지 확인하세요.")
