"""
MediaPipe FaceLandmarker blendshape 기반 실시간 시선 추적.
투명 NSWindow 오버레이로 시선 점을 표시하고,
응시 창이 확정되면 커서를 해당 창으로 이동한다.

사용법:
    python gaze_overlay.py
    Ctrl+C로 종료
"""

import json
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import objc
from Cocoa import (
    NSApplication, NSWindow, NSColor, NSScreen, NSView, NSBezierPath,
    NSBackingStoreBuffered, NSFloatingWindowLevel, NSMakeRect,
    NSRunLoop, NSDate,
)
from Quartz import CGWarpMouseCursorPosition, CGEventCreate, CGEventGetLocation

from list_windows import list_windows

MODEL_PATH = "face_landmarker.task"
BLINK_THRESHOLD = 0.5
SMOOTHING_ALPHA = 0.3
DWELL_SECONDS = 0.25
WINDOW_REFRESH_SECONDS = 1.0
DOT_RADIUS = 18
MOUSE_IDLE_SECONDS = 1.5
MOUSE_MOVE_THRESHOLD = 5
CORRECTION_ALPHA = 0.2
MIN_CORRECTIONS = 3


class DotView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(DotView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.point = (0.0, 0.0)
        self.confirmed = False
        return self

    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(rect)
        color = NSColor.greenColor() if self.confirmed else NSColor.orangeColor()
        color.set()
        x, y = self.point
        oval = NSMakeRect(x - DOT_RADIUS, y - DOT_RADIUS, DOT_RADIUS * 2, DOT_RADIUS * 2)
        NSBezierPath.bezierPathWithOvalInRect_(oval).fill()


def make_overlay():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)
    app.activateIgnoringOtherApps_(True)
    screen_frame = NSScreen.mainScreen().frame()
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        screen_frame, 0, NSBackingStoreBuffered, False
    )
    window.setOpaque_(False)
    window.setBackgroundColor_(NSColor.clearColor())
    window.setLevel_(NSFloatingWindowLevel)
    window.setIgnoresMouseEvents_(True)
    window.setHasShadow_(False)
    window.setCollectionBehavior_(1 << 0 | 1 << 8)
    view = DotView.alloc().initWithFrame_(screen_frame)
    window.setContentView_(view)
    window.makeKeyAndOrderFront_(None)
    window.orderFrontRegardless()
    return app, window, view


def make_landmarker():
    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        output_face_blendshapes=True,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
    )
    return vision.FaceLandmarker.create_from_options(options)


def get_feature(landmarker, frame, frame_idx, fps=30):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    timestamp_ms = int(frame_idx * (1000 / fps))
    result = landmarker.detect_for_video(mp_image, timestamp_ms)

    if not result.face_blendshapes:
        return None

    shapes = {c.category_name: c.score for c in result.face_blendshapes[0]}
    if shapes.get("eyeBlinkLeft", 0) > BLINK_THRESHOLD or shapes.get("eyeBlinkRight", 0) > BLINK_THRESHOLD:
        return None

    horiz = (shapes.get("eyeLookOutLeft", 0) + shapes.get("eyeLookInRight", 0)) \
          - (shapes.get("eyeLookInLeft", 0)  + shapes.get("eyeLookOutRight", 0))
    vert  = (shapes.get("eyeLookUpLeft", 0)  + shapes.get("eyeLookUpRight", 0)) \
          - (shapes.get("eyeLookDownLeft", 0) + shapes.get("eyeLookDownRight", 0))
    return horiz, vert


def find_window_at(point, windows):
    x, y = point
    for w in windows:
        if w["x"] <= x <= w["x"] + w["width"] and w["y"] <= y <= w["y"] + w["height"]:
            return w
    return None


def window_key(w):
    return (w["owner"], w["name"], w["x"], w["y"])


def main():
    with open("calibration.json") as f:
        calib = json.load(f)
    A_T = np.array(calib["A_T"])
    screen_w, screen_h = calib["screen_w"], calib["screen_h"]

    app, window, view = make_overlay()
    cap = cv2.VideoCapture(0)
    landmarker = make_landmarker()

    frame_idx = 0
    smoothed = None
    windows = list_windows()
    last_window_refresh = time.time()

    candidate_key = None
    candidate_since = None
    confirmed_key = None

    correction = np.array([0.0, 0.0])
    correction_count = 0

    def get_cursor_pos():
        loc = CGEventGetLocation(CGEventCreate(None))
        return loc.x, loc.y

    last_cursor_pos = get_cursor_pos()
    last_user_move_time = time.time()
    we_just_moved = False

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            now = time.time()

            current_cursor = get_cursor_pos()
            dx = current_cursor[0] - last_cursor_pos[0]
            dy = current_cursor[1] - last_cursor_pos[1]
            if not we_just_moved and (dx ** 2 + dy ** 2) ** 0.5 > MOUSE_MOVE_THRESHOLD:
                last_user_move_time = now
            we_just_moved = False
            last_cursor_pos = current_cursor

            if now - last_window_refresh > WINDOW_REFRESH_SECONDS:
                windows = list_windows()
                last_window_refresh = now

            feat = get_feature(landmarker, frame, frame_idx)
            frame_idx += 1
            if feat is None:
                continue

            v = np.array([feat[0], feat[1], feat[1] ** 2, 1.0])
            raw_x, raw_y = v @ A_T
            if correction_count >= MIN_CORRECTIONS:
                raw_x += correction[0]
                raw_y += correction[1]

            if smoothed is None:
                smoothed = np.array([raw_x, raw_y])
            else:
                smoothed = SMOOTHING_ALPHA * np.array([raw_x, raw_y]) + (1 - SMOOTHING_ALPHA) * smoothed

            point = (
                float(np.clip(smoothed[0], 0, screen_w - 1)),
                float(np.clip(smoothed[1], 0, screen_h - 1)),
            )

            hit = find_window_at(point, windows)
            key = window_key(hit) if hit else None

            if key != candidate_key:
                candidate_key = key
                candidate_since = now
            elif candidate_since is not None and (now - candidate_since) >= DWELL_SECONDS:
                if key != confirmed_key:
                    confirmed_key = key
                    label = hit["owner"] if hit else "(없음)"
                    print(f"[타겟 전환] {label} {hit['name'] if hit else ''}")
                    if hit:
                        cx = hit["x"] + hit["width"] / 2
                        cy = hit["y"] + hit["height"] / 2
                        if smoothed is not None:
                            error = np.array([cx, cy]) - smoothed
                            correction = CORRECTION_ALPHA * error + (1 - CORRECTION_ALPHA) * correction
                            correction_count += 1
                        if (now - last_user_move_time) >= MOUSE_IDLE_SECONDS:
                            CGWarpMouseCursorPosition((cx, cy))
                            last_cursor_pos = (cx, cy)
                            we_just_moved = True

            view.point = point
            view.confirmed = (confirmed_key == key)
            view.setNeedsDisplay_(True)
            window.displayIfNeeded()
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.0))

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()


if __name__ == "__main__":
    main()
