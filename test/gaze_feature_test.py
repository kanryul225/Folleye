"""
캘리브레이션 전 사전 점검: 눈동자가 눈 안에서 어디 위치하는지를
0~1 비율(horiz, vert)로 뽑아서 실시간으로 화면에 찍어본다.
좌우/위아래로 눈만 움직였을 때 이 숫자가 의미 있게 변하는지 확인하는 게 목적.

사용법:
    python gaze_feature_test.py
    'q' 누르면 종료
"""

import cv2
import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh

# (바깥쪽 구석, 안쪽 구석, 윗눈꺼풀, 아랫눈꺼풀, 눈동자 중심)
LEFT_EYE = (33, 133, 159, 145, 468)
RIGHT_EYE = (263, 362, 386, 374, 473)


def eye_ratio(landmarks, indices, w, h):
    outer, inner, top, bottom, iris = indices
    ox, oy = landmarks[outer].x * w, landmarks[outer].y * h
    ix, iy = landmarks[inner].x * w, landmarks[inner].y * h
    tx, ty = landmarks[top].x * w, landmarks[top].y * h
    bx, by = landmarks[bottom].x * w, landmarks[bottom].y * h
    px, py = landmarks[iris].x * w, landmarks[iris].y * h

    horiz = (px - ix) / (ox - ix) if (ox - ix) != 0 else 0.5
    vert = (py - ty) / (by - ty) if (by - ty) != 0 else 0.5
    return horiz, vert


cap = cv2.VideoCapture(0)

with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
) as face_mesh:

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            lh, lv = eye_ratio(landmarks, LEFT_EYE, w, h)
            rh, rv = eye_ratio(landmarks, RIGHT_EYE, w, h)
            horiz = (lh + rh) / 2
            vert = (lv + rv) / 2

            cv2.putText(frame, f"horiz={horiz:.2f} vert={vert:.2f}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Gaze Feature Test", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cap.release()
cv2.destroyAllWindows()
