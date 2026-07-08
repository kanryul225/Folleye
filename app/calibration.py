import json
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import objc
from Cocoa import (
    NSWindow, NSColor, NSScreen, NSView, NSBezierPath,
    NSBackingStoreBuffered, NSFloatingWindowLevel, NSMakeRect,
    NSRunLoop, NSDate,
)

from .utils import resource_path

SETTLE_SECONDS = 1.0
COLLECT_SECONDS = 1.0
BLINK_THRESHOLD = 0.5
DOT_RADIUS = 25


class _CalibView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_CalibView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.point = (0.0, 0.0)
        self.settled = False
        return self

    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        NSColor.blackColor().set()
        NSBezierPath.fillRect_(rect)
        color = NSColor.greenColor() if self.settled else NSColor.redColor()
        color.set()
        x, y = self.point
        oval = NSMakeRect(x - DOT_RADIUS, y - DOT_RADIUS, DOT_RADIUS * 2, DOT_RADIUS * 2)
        NSBezierPath.bezierPathWithOvalInRect_(oval).fill()


def _make_window():
    screen_frame = NSScreen.mainScreen().frame()
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        screen_frame, 0, NSBackingStoreBuffered, False
    )
    window.setOpaque_(True)
    window.setLevel_(NSFloatingWindowLevel)
    window.setIgnoresMouseEvents_(True)
    window.setHasShadow_(False)
    view = _CalibView.alloc().initWithFrame_(screen_frame)
    window.setContentView_(view)
    window.makeKeyAndOrderFront_(None)
    window.orderFrontRegardless()
    screen_w = int(screen_frame.size.width)
    screen_h = int(screen_frame.size.height)
    return window, view, screen_w, screen_h


def _render(window, view):
    view.setNeedsDisplay_(True)
    window.displayIfNeeded()
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.0))


def _make_landmarker():
    base_options = mp_python.BaseOptions(
        model_asset_path=str(resource_path("face_landmarker.task"))
    )
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        output_face_blendshapes=True,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
    )
    return vision.FaceLandmarker.create_from_options(options)


def _get_feature(landmarker, frame, frame_idx):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect_for_video(mp_image, int(frame_idx * 33))

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


def run_calibration(save_path="calibration.json", on_complete=None, on_cancel=None):
    """캘리브레이션을 실행하고 결과를 save_path에 저장한다.
    on_complete: 성공 시 호출되는 콜백
    on_cancel: 취소/실패 시 호출되는 콜백
    """
    window, view, screen_w, screen_h = _make_window()

    margin_x = screen_w * 0.1
    margin_y = screen_h * 0.1
    xs = [margin_x, screen_w / 2, screen_w - margin_x]
    ys = [margin_y, screen_h * 0.3, screen_h / 2, screen_h * 0.7, screen_h - margin_y]
    targets = [(x, y) for y in ys for x in xs]  # 3×5 = 15개

    cap = cv2.VideoCapture(0)
    landmarker = _make_landmarker()

    features = []
    collected_targets = []
    frame_idx = 0
    aborted = False

    try:
        for (tx, ty) in targets:
            start = time.time()
            samples = []

            while True:
                ok, frame = cap.read()
                if not ok:
                    continue
                elapsed = time.time() - start

                view.point = (tx, ty)
                view.settled = elapsed >= SETTLE_SECONDS
                _render(window, view)

                if elapsed >= SETTLE_SECONDS:
                    feat = _get_feature(landmarker, frame, frame_idx)
                    frame_idx += 1
                    if feat is not None:
                        samples.append(feat)

                if elapsed >= SETTLE_SECONDS + COLLECT_SECONDS:
                    break

            if samples:
                median_feat = np.median(np.array(samples), axis=0)
                features.append(median_feat)
                collected_targets.append((tx, ty))
                print(f"  ({tx:.0f},{ty:.0f}) samples={len(samples)} feat={np.round(median_feat, 3)}")
            else:
                print(f"  ({tx:.0f},{ty:.0f}) 샘플 없음 — 건너뜀")

    except KeyboardInterrupt:
        aborted = True
    finally:
        cap.release()
        window.orderOut_(None)

    if aborted or len(features) < 6:
        print("캘리브레이션 취소 또는 데이터 부족.")
        if on_cancel:
            on_cancel()
        return

    X = np.array([[f[0], f[1], f[1] ** 2, 1.0] for f in features])
    Y = np.array(collected_targets)
    A_T, *_ = np.linalg.lstsq(X, Y, rcond=None)

    error = np.linalg.norm(X @ A_T - Y, axis=1)
    print(f"캘리브레이션 완료 — 평균 오차 {error.mean():.1f}px, 최대 {error.max():.1f}px")

    with open(save_path, "w") as f:
        json.dump({"A_T": A_T.tolist(), "screen_w": screen_w, "screen_h": screen_h}, f, indent=2)

    if on_complete:
        on_complete()
