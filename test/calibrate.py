"""
캘리브레이션: MediaPipe FaceLandmarker blendshape 기반 시선 feature(horiz, vert)를 추출하고,
화면 좌표로 매핑하는 선형회귀 행렬 A_T를 만든다.

사용법:
    python calibrate.py
    각 점이 뜨면 그 점을 보고 있으면 됨 (자동 진행)
    Ctrl+C로 중단
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

MODEL_PATH = "face_landmarker.task"
SETTLE_SECONDS = 1.0
COLLECT_SECONDS = 1.0
BLINK_THRESHOLD = 0.5
DOT_RADIUS = 25


class CalibView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(CalibView, self).initWithFrame_(frame)
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


def make_window():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)
    app.activateIgnoringOtherApps_(True)
    screen_frame = NSScreen.mainScreen().frame()
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        screen_frame, 0, NSBackingStoreBuffered, False
    )
    window.setOpaque_(True)
    window.setLevel_(NSFloatingWindowLevel)
    window.setIgnoresMouseEvents_(True)
    window.setHasShadow_(False)
    view = CalibView.alloc().initWithFrame_(screen_frame)
    window.setContentView_(view)
    window.makeKeyAndOrderFront_(None)
    window.orderFrontRegardless()
    screen_w = int(screen_frame.size.width)
    screen_h = int(screen_frame.size.height)
    return window, view, screen_w, screen_h


def render(window, view):
    view.setNeedsDisplay_(True)
    window.displayIfNeeded()
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.0))


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


def main():
    window, view, screen_w, screen_h = make_window()

    margin_x, margin_y = screen_w * 0.1, screen_h * 0.1
    xs = [margin_x, screen_w / 2, screen_w - margin_x]
    ys = [margin_y, screen_h * 0.3, screen_h / 2, screen_h * 0.7, screen_h - margin_y]
    targets = [(x, y) for y in ys for x in xs]  # 3×5 = 15개

    cap = cv2.VideoCapture(0)
    landmarker = make_landmarker()

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
                render(window, view)

                if elapsed >= SETTLE_SECONDS:
                    feat = get_feature(landmarker, frame, frame_idx)
                    frame_idx += 1
                    if feat is not None:
                        samples.append(feat)

                if elapsed >= SETTLE_SECONDS + COLLECT_SECONDS:
                    break

            if samples:
                median_feat = np.median(np.array(samples), axis=0)
                features.append(median_feat)
                collected_targets.append((tx, ty))
                print(f"target=({tx:.0f},{ty:.0f}) samples={len(samples)} feature={median_feat}")
            else:
                print(f"target=({tx:.0f},{ty:.0f}) 샘플 없음 (얼굴 감지 실패?)")

    except KeyboardInterrupt:
        aborted = True

    cap.release()

    if aborted:
        print("캘리브레이션 중단됨.")
        return

    if len(features) < 6:
        print("유효한 포인트가 너무 적습니다. 다시 시도해주세요.")
        return

    X = np.array([[f[0], f[1], f[1] ** 2, 1.0] for f in features])  # (N, 4)
    Y = np.array(collected_targets)                                    # (N, 2)
    A_T, *_ = np.linalg.lstsq(X, Y, rcond=None)                      # (4, 2)

    pred = X @ A_T
    error = np.linalg.norm(pred - Y, axis=1)
    print(f"캘리브레이션 완료. 평균 오차: {error.mean():.1f}px, 최대 오차: {error.max():.1f}px")

    with open("calibration.json", "w") as f:
        json.dump({"A_T": A_T.tolist(), "screen_w": screen_w, "screen_h": screen_h}, f, indent=2)
    print("calibration.json 저장 완료.")


if __name__ == "__main__":
    main()
