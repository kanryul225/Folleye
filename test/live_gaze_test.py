"""
calibration.json을 불러와서, 실시간으로 예측된 시선 좌표를 화면에 점으로 그려본다.
캘리브레이션이 실제로 잘 됐는지 눈으로 확인하는 용도.

사용법:
    python live_gaze_test.py
    화면을 이리저리 보면서 초록 점이 따라오는지 확인. 'esc'로 종료.
"""

import json

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_PATH = "face_landmarker.task"
WIN = "live gaze test"
BLINK_THRESHOLD = 0.5
SMOOTHING_ALPHA = 0.3  # 0~1, 클수록 최근 값에 더 민감(덜 부드러움)


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

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

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

            x_clamped = int(np.clip(smoothed[0], 0, screen_w - 1))
            y_clamped = int(np.clip(smoothed[1], 0, screen_h - 1))

            cv2.circle(canvas, (x_clamped, y_clamped), 20, (0, 255, 0), -1)
            cv2.putText(canvas, f"raw=({raw_x:.0f},{raw_y:.0f})", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow(WIN, canvas)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
