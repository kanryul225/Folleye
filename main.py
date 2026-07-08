import sys
import traceback

print("[Folleye] 시작 중...", flush=True)

try:
    from app.menubar import FolleyeApp
    print("[Folleye] 모듈 로드 완료", flush=True)
    app = FolleyeApp()
    print("[Folleye] 앱 초기화 완료 — 메뉴바에서 👁 확인하세요", flush=True)
    app.run()
except Exception:
    print("[Folleye] 오류 발생:", flush=True)
    traceback.print_exc()
    sys.exit(1)
