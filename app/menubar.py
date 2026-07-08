import os
import time
import pathlib

import objc
from Cocoa import (
    NSApplication, NSObject, NSStatusBar, NSVariableStatusItemLength,
    NSMenu, NSMenuItem, NSTimer, NSImage,
)

_IMAGE_DIR = pathlib.Path(__file__).parent.parent / "image"

from .overlay import GazeOverlay
from .gaze_engine import GazeEngine
from .windows import list_windows, window_at, window_key, get_cursor_pos, move_cursor
from .calibration import run_calibration
from .onboarding import show_onboarding

DWELL_SECONDS = 0.25
WINDOW_REFRESH_SECONDS = 1.0
MOUSE_IDLE_SECONDS = 1.5
MOUSE_MOVE_THRESHOLD = 5

CALIB_PATH = "calibration.json"


class _AppDelegate(NSObject):
    def initWithApp_(self, app):
        self = objc.super(_AppDelegate, self).init()
        if self is None:
            return None
        self._app = app
        return self

    def toggleTracking_(self, sender):
        self._app.toggle_tracking()

    def startCalibration_(self, sender):
        self._app.open_calibration_ui()

    def toggleOverlay_(self, sender):
        self._app.toggle_overlay()

    def quitApp_(self, sender):
        self._app.quit()

    def tick_(self, timer):
        self._app._tick()


class FolleyeApp:
    def __init__(self):
        self._ns_app = NSApplication.sharedApplication()
        self._ns_app.setActivationPolicy_(1)

        self._engine = GazeEngine()
        self._overlay = GazeOverlay()
        self._overlay_enabled = False  # 기본 꺼짐

        self._candidate_key = None
        self._candidate_since = None
        self._confirmed_key = None
        self._windows = []
        self._last_window_refresh = 0.0

        self._last_cursor_pos = get_cursor_pos()
        self._last_user_move_time = time.time()
        self._we_just_moved = False

        self._delegate = _AppDelegate.alloc().initWithApp_(self)
        self._setup_menubar()

        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.01, self._delegate, "tick:", None, True
        )

        self._onboarding = show_onboarding(
            on_calibrate=self.start_calibration,
            on_start_tracking=self._start_tracking,
        )

    def _setup_menubar(self):
        self._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        icon = NSImage.alloc().initWithContentsOfFile_(str(_IMAGE_DIR / "logo_white.png"))
        icon.setSize_((27, 18))
        btn = self._status_item.button()
        btn.setImage_(icon)
        btn.setTitle_("")

        self._menu = NSMenu.alloc().init()

        self._track_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Start Tracking", "toggleTracking:", ""
        )
        self._calib_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Calibration", "startCalibration:", ""
        )
        self._overlay_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Gaze Dot", "toggleOverlay:", ""
        )
        self._overlay_item.setState_(0)  # 기본 off (체크 없음)

        self._quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", ""
        )

        for item in (self._track_item, self._calib_item,
                     self._overlay_item, self._quit_item):
            item.setTarget_(self._delegate)

        self._menu.addItem_(self._track_item)
        self._menu.addItem_(self._calib_item)
        self._menu.addItem_(NSMenuItem.separatorItem())
        self._menu.addItem_(self._overlay_item)
        self._menu.addItem_(NSMenuItem.separatorItem())
        self._menu.addItem_(self._quit_item)
        self._status_item.setMenu_(self._menu)

    # ── 메뉴 액션 ────────────────────────────────────────────

    def toggle_tracking(self):
        if self._engine.is_running:
            self._stop_tracking()
        else:
            self._start_tracking()

    def _start_tracking(self):
        if not os.path.exists(CALIB_PATH):
            print("[Folleye] No calibration found — run calibration first.", flush=True)
            return
        self._engine.load_calibration(CALIB_PATH)
        self._engine.start()
        if self._overlay_enabled:
            self._overlay.show()
        self._track_item.setTitle_("Stop Tracking")
        self._candidate_key = None
        self._candidate_since = None
        self._confirmed_key = None
        self._windows = list_windows()
        self._last_window_refresh = time.time()

    def _stop_tracking(self):
        self._engine.stop()
        self._overlay.hide()
        self._track_item.setTitle_("Start Tracking")

    def toggle_overlay(self):
        self._overlay_enabled = not self._overlay_enabled
        self._overlay_item.setState_(1 if self._overlay_enabled else 0)
        if self._engine.is_running:
            if self._overlay_enabled:
                self._overlay.show()
            else:
                self._overlay.hide()

    def open_calibration_ui(self):
        if self._engine.is_running:
            self._stop_tracking()
        self._onboarding.show_calib_prep()

    def start_calibration(self):
        run_calibration(save_path=CALIB_PATH)

    def quit(self):
        self._timer.invalidate()
        self._engine.stop()
        self._ns_app.terminate_(None)

    # ── NSTimer 틱 ───────────────────────────────────────────

    def run(self):
        self._ns_app.run()

    def _tick(self):
        if not self._engine.is_running:
            return

        now = time.time()

        cur = get_cursor_pos()
        dx = cur[0] - self._last_cursor_pos[0]
        dy = cur[1] - self._last_cursor_pos[1]
        if not self._we_just_moved and (dx**2 + dy**2) ** 0.5 > MOUSE_MOVE_THRESHOLD:
            self._last_user_move_time = now
        self._we_just_moved = False
        self._last_cursor_pos = cur

        if now - self._last_window_refresh > WINDOW_REFRESH_SECONDS:
            self._windows = list_windows()
            self._last_window_refresh = now

        try:
            data = self._engine.out_queue.get_nowait()
        except Exception:
            return

        point = data["point"]
        smoothed = data["smoothed"]

        hit = window_at(point, self._windows)
        key = window_key(hit) if hit else None

        if key != self._candidate_key:
            self._candidate_key = key
            self._candidate_since = now
        elif self._candidate_since and (now - self._candidate_since) >= DWELL_SECONDS:
            if key != self._confirmed_key:
                self._confirmed_key = key
                if hit:
                    cx = hit["x"] + hit["width"] / 2
                    cy = hit["y"] + hit["height"] / 2
                    self._engine.update_correction((cx, cy), smoothed)
                    if (now - self._last_user_move_time) >= MOUSE_IDLE_SECONDS:
                        move_cursor(cx, cy)
                        self._last_cursor_pos = (cx, cy)
                        self._we_just_moved = True

        if self._overlay_enabled:
            self._overlay.update(point, confirmed=(self._confirmed_key == key))
