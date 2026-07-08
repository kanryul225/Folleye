import json
import queue
import threading

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .utils import resource_path

BLINK_THRESHOLD = 0.5
SMOOTHING_ALPHA = 0.3
CORRECTION_ALPHA = 0.2
MIN_CORRECTIONS = 3


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


def _get_feature(landmarker, frame, frame_idx, fps=30):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect_for_video(mp_image, int(frame_idx * (1000 / fps)))

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


class GazeEngine:
    """백그라운드 스레드에서 카메라 → 시선 좌표를 계산해 queue에 넣는다."""

    def __init__(self):
        self.out_queue = queue.Queue(maxsize=1)   # 최신 프레임만 유지
        self._stop = threading.Event()
        self._thread = None
        self.A_T = None
        self.screen_w = None
        self.screen_h = None
        self.correction = np.array([0.0, 0.0])
        self.correction_count = 0

    def load_calibration(self, path="calibration.json"):
        with open(path) as f:
            calib = json.load(f)
        self.A_T = np.array(calib["A_T"])
        self.screen_w = calib["screen_w"]
        self.screen_h = calib["screen_h"]

    def update_correction(self, window_center, smoothed):
        """창이 확정될 때 drift 보정값 업데이트."""
        error = np.array(window_center) - smoothed
        self.correction = CORRECTION_ALPHA * error + (1 - CORRECTION_ALPHA) * self.correction
        self.correction_count += 1

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        cap = cv2.VideoCapture(0)
        landmarker = _make_landmarker()
        frame_idx = 0
        smoothed = None

        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                continue

            feat = _get_feature(landmarker, frame, frame_idx)
            frame_idx += 1
            if feat is None:
                continue

            v = np.array([feat[0], feat[1], feat[1] ** 2, 1.0])
            raw_x, raw_y = v @ self.A_T
            if self.correction_count >= MIN_CORRECTIONS:
                raw_x += self.correction[0]
                raw_y += self.correction[1]

            if smoothed is None:
                smoothed = np.array([raw_x, raw_y])
            else:
                smoothed = SMOOTHING_ALPHA * np.array([raw_x, raw_y]) + (1 - SMOOTHING_ALPHA) * smoothed

            point = (
                float(np.clip(smoothed[0], 0, self.screen_w - 1)),
                float(np.clip(smoothed[1], 0, self.screen_h - 1)),
            )

            try:
                self.out_queue.put_nowait({"point": point, "smoothed": smoothed.copy()})
            except queue.Full:
                pass

        cap.release()
