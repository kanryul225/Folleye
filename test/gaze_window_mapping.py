"""
실시간 시선 좌표를 1단계의 창 bounding box와 결합해서,
"지금 사용자가 어떤 창을 보고 있는지"를 판정한다.

떨림(saccade) 때문에 매 프레임 바뀌는 걸 그대로 믿지 않고,
같은 창을 DWELL_SECONDS 이상 계속 가리켜야 "확정된 타겟 창"으로 인정한다.

사용법:
    python gaze_window_mapping.py
    화면의 여러 창을 보면서, 콘솔에 타겟 창이 바뀔 때마다 로그가 찍히는지 확인.
    'esc'로 종료.
"""

import json
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from list_windows import list_windows

MODEL_PATH = "face_landmarker.task"
WIN = "gaze window mapping"
BLINK_THRESHOLD = 0.5
SMOOTHING_ALPHA = 0.3
DWELL_SECONDS = 0.25       # 같은 창을 이만큼 계속 봐야 타겟으로 확정
WINDOW_REFRESH_SECONDS = 1.0  # 창 목록을 다시 가져오는 주기


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

    look_out_l = shapes.get("eyeLookOutLeft", 0)
    look_in_l = shapes.get("eyeLookInLeft", 0)
    look_out_r = shapes.get("eyeLookOutRight", 0)
    look_in_r = shapes.get("eyeLookInRight", 0)
    look_up_l = shapes.get("eyeLookUpLeft", 0)
    look_down_l = shapes.get("eyeLookDownLeft", 0)
    look_up_r = shapes.get("eyeLookUpRight", 0)
    look_down_r = shapes.get("eyeLookDownRight", 0)

    horiz = (look_out_l + look_in_r) - (look_in_l + look_out_r)
    vert = (look_up_l + look_up_r) - (look_down_l + look_down_r)
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

    cap = cv2.VideoCapture(0)
    landmarker = make_landmarker()

    cv2.namedWindow(WIN, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    frame_idx = 0
    smoothed = None
    windows = list_windows()
    last_window_refresh = time.time()

    candidate_key = None
    candidate_since = None
    confirmed_key = None

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        now = time.time()
        if now - last_window_refresh > WINDOW_REFRESH_SECONDS:
            windows = list_windows()
            last_window_refresh = now

        feat = get_feature(landmarker, frame, frame_idx)
        frame_idx += 1

        canvas = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)

        if feat is not None:
            v = np.array([feat[0], feat[1], feat[1] ** 2, 1.0])
            raw_x, raw_y = v @ A_T

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

            color = (0, 255, 0) if confirmed_key == key else (0, 165, 255)
            cv2.circle(canvas, (int(point[0]), int(point[1])), 20, color, -1)
            label = confirmed_key[0] if confirmed_key else "(없음)"
            cv2.putText(canvas, f"target: {label}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow(WIN, canvas)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
