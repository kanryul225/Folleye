"""
랜드마크 비율 방식이 신호가 너무 약했을 때의 대안 테스트.
MediaPipe의 사전 학습된 blendshape(Apple ARKit 방식과 유사)으로
'눈이 좌/우/상/하를 보는 정도'를 직접 점수로 받아본다.

사용법:
    python gaze_blendshape_test.py
    'q' 누르면 종료
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_PATH = "face_landmarker.task"

base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=True,
    running_mode=vision.RunningMode.VIDEO,
    num_faces=1,
)
landmarker = vision.FaceLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)
fps = 30
frame_idx = 0

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    timestamp_ms = int(frame_idx * (1000 / fps))
    result = landmarker.detect_for_video(mp_image, timestamp_ms)
    frame_idx += 1

    if result.face_blendshapes:
        shapes = {c.category_name: c.score for c in result.face_blendshapes[0]}

        look_out_l = shapes.get("eyeLookOutLeft", 0)
        look_in_l = shapes.get("eyeLookInLeft", 0)
        look_out_r = shapes.get("eyeLookOutRight", 0)
        look_in_r = shapes.get("eyeLookInRight", 0)
        look_up_l = shapes.get("eyeLookUpLeft", 0)
        look_down_l = shapes.get("eyeLookDownLeft", 0)
        look_up_r = shapes.get("eyeLookUpRight", 0)
        look_down_r = shapes.get("eyeLookDownRight", 0)

        # 오른쪽을 볼 때 + 가 되도록: 왼쪽 눈이 바깥(오른쪽 방향)으로 도는 정도
        # + 오른쪽 눈이 안쪽(오른쪽 방향)으로 도는 정도, 반대 방향은 빼줌
        horiz = (look_out_l + look_in_r) - (look_in_l + look_out_r)
        vert = (look_up_l + look_up_r) - (look_down_l + look_down_r)

        cv2.putText(frame, f"horiz={horiz:.2f} vert={vert:.2f}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Blendshape Gaze Test", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
