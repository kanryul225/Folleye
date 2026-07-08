"""
0단계 스파이크: 커서를 움직이지 않고, 지정한 화면 좌표(다른 창 위치)로
합성 스크롤 이벤트를 보냈을 때 그 창이 실제로 스크롤되는지 확인한다.

사용법:
1. GoodNotes나 ChatGPT 같은 타겟 앱 창을 화면에 띄운다.
2. 그 창 안쪽의 좌표를 TARGET_X, TARGET_Y 에 적는다.
   (좌표 모를 때는 아래 print_mouse_position() 으로 마우스를 그 창 위에
   잠깐 올렸다가 좌표를 읽어서 적으면 된다.)
3. python spike_scroll_inject.py 실행
4. 마우스는 다른 곳(예: 빈 데스크탑)에 가만히 두고 콘솔에서 엔터를 친다.
5. 타겟 창이 스크롤되는지 눈으로 확인한다.
"""

import Quartz
import time

TARGET_X = 1496
TARGET_Y = 342  
SCROLL_AMOUNT = -200  # 음수: 아래로 스크롤


def print_mouse_position(seconds=3):
    print(f"{seconds}초 동안 마우스 위치를 출력합니다. 확인하고 싶은 창 위에 마우스를 올려보세요.")
    for _ in range(seconds * 2):
        loc = Quartz.NSEvent.mouseLocation()
        screen_height = Quartz.CGDisplayPixelsHigh(Quartz.CGMainDisplayID())
        flipped_y = screen_height - loc.y
        print(f"x={loc.x:.0f}, y={flipped_y:.0f}")
        time.sleep(0.5)


def inject_scroll(x, y, amount):
    event = Quartz.CGEventCreateScrollWheelEvent(
        None,
        Quartz.kCGScrollEventUnitPixel,
        1,
        amount,
    )
    Quartz.CGEventSetLocation(event, Quartz.CGPoint(x=x, y=y))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


if __name__ == "__main__":
    choice = input("좌표 확인 모드로 실행할까요? (y/n): ").strip().lower()
    if choice == "y":
        print_mouse_position()
    else:
        input(f"마우스를 다른 곳에 두고 엔터를 누르면 ({TARGET_X}, {TARGET_Y}) 위치로 스크롤 이벤트를 보냅니다...")
        inject_scroll(TARGET_X, TARGET_Y, SCROLL_AMOUNT)
        print("스크롤 이벤트 전송 완료. 타겟 창이 스크롤됐는지 확인하세요.")
