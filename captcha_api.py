"""
Cognitive CAPTCHA API Server (FastAPI)
Принимает кадры от браузера, анализирует взгляд, сохраняет токен в PostgreSQL.
"""

import cv2
import numpy as np
import base64
import uuid
import time
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Импортируем твой скоринг (убедись, что файл лежит в папке cognitive_capcha)
from analysis.scorer import score_stimulus

# === НАСТРОЙКИ ===
DB_CONFIG = {
    "dbname": "****",
    "user": " ***** "
    "password": " ***** "
    "host": "localhost",
    "port": "5432"
}

# Размеры экрана (должны совпадать с JS и Java)
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
SESSION_THRESHOLD = 0.3 # порог принятия решения

# MediaPipe
import mediapipe as mp
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1, refine_landmarks=True,
    min_detection_confidence=0.5, min_tracking_confidence=0.5
)

# Координаты целей (как в JS)
TARGET_COORDS = {
    "top_left": (100, 100), "top_right": (1820, 100),
    "center": (960, 540), "bottom_left": (100, 980), "bottom_right": (1820, 980)
}

app = FastAPI(title="Cognitive CAPTCHA API")

# Разрешаем запросы с React (3000) и Java (8080)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Временное хранилище сессий калибровки в памяти
active_sessions = {}

# === МОДЕЛИ ЗАПРОСОВ ===
class CalibrateRequest(BaseModel):
    frames_by_target: Dict[str, List[str]] # { "top_left": ["base64...", ...], ... }

class VerifyRequest(BaseModel):
    session_id: str
    frames_by_target: Dict[str, List[str]]
    sequence: List[str]

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def decode_base64_image(b64_str: str) -> Optional[np.ndarray]:
    """Декодирует Base64 строку в OpenCV изображение (numpy array)."""
    try:
        if ',' in b64_str:
            b64_str = b64_str.split(',')[1]
        img_data = base64.b64decode(b64_str)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"[ERROR] Decode failed: {e}")
        return None

def get_gaze_from_frame(frame: np.ndarray) -> Optional[tuple]:
    """
    Вычисляет нормализованные координаты взгляда через отношение
    позиции зрачка к размеру глаза.
    ИСПОЛЬЗУЕТ ТУ ЖЕ ФОРМУЛУ, ЧТО И ДЕСКТОПНАЯ ВЕРСИЯ!
    """
    if frame is None:
        return None

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    if not results.multi_face_landmarks:
        return None

    landmarks = results.multi_face_landmarks[0].landmark
    h, w, _ = frame.shape

    # === ЛЕВЫЙ ГЛАЗ ===
    left_iris = landmarks[468]
    left_eye_left = landmarks[33]
    left_eye_right = landmarks[133]
    left_eye_top = landmarks[159]
    left_eye_bottom = landmarks[145]

    # Пиксельные координаты
    iris_x = left_iris.x * w
    iris_y = left_iris.y * h

    eye_width = abs(left_eye_right.x - left_eye_left.x) * w
    eye_height = abs(left_eye_bottom.y - left_eye_top.y) * h

    # ЦЕНТР глаза (как в десктопной версии!)
    eye_center_x = (left_eye_left.x + left_eye_right.x) / 2.0 * w
    eye_center_y = (left_eye_top.y + left_eye_bottom.y) / 2.0 * h

    # ratio = смещение от ЦЕНТРА (как в десктопной версии!)
    left_ratio_x = (iris_x - eye_center_x) / (eye_width / 2.0)
    left_ratio_y = (iris_y - eye_center_y) / (eye_height / 2.0)

    # === ПРАВЫЙ ГЛАЗ ===
    right_iris = landmarks[473]
    right_eye_left = landmarks[362]
    right_eye_right = landmarks[263]
    right_eye_top = landmarks[386]
    right_eye_bottom = landmarks[374]

    right_iris_x = right_iris.x * w
    right_iris_y = right_iris.y * h

    right_eye_width = abs(right_eye_right.x - right_eye_left.x) * w
    right_eye_height = abs(right_eye_bottom.y - right_eye_top.y) * h

    right_eye_center_x = (right_eye_left.x + right_eye_right.x) / 2.0 * w
    right_eye_center_y = (right_eye_top.y + right_eye_bottom.y) / 2.0 * h

    right_ratio_x = (right_iris_x - right_eye_center_x) / (right_eye_width / 2.0)
    right_ratio_y = (right_iris_y - right_eye_center_y) / (right_eye_height / 2.0)

    # === УСРЕДНЕНИЕ ===
    avg_ratio_x = (left_ratio_x + right_ratio_x) / 2.0
    avg_ratio_y = (left_ratio_y + right_ratio_y) / 2.0

    # === ОТЛАДКА ===
    print(f"  [DEBUG] ratio_x={avg_ratio_x:.3f}, ratio_y={avg_ratio_y:.3f}")

    # === НОРМАЛИЗАЦИЯ (как в десктопной версии!) ===
    gaze_x = np.clip((avg_ratio_x + 1.0) / 2.0, 0.0, 1.0)
    gaze_y = np.clip((avg_ratio_y + 1.0) / 2.0, 0.0, 1.0)

    # Инверсия X для зеркала (как в десктопной версии!)
    gaze_x = 1.0 - gaze_x

    print(f"  [DEBUG] normalized: gaze_x={gaze_x:.3f}, gaze_y={gaze_y:.3f}")

    return (gaze_x, gaze_y)

def calculate_calibration(gaze_data: Dict[str, tuple]) -> Dict[str, float]:
    """Считает коэффициенты калибровки (scale, offset) и применяет защиту от инверсии Y."""
    # Берем точки слева и справа для X
    tl = gaze_data.get("top_left", (0.5, 0.5))
    tr = gaze_data.get("top_right", (0.5, 0.5))
    bl = gaze_data.get("bottom_left", (0.5, 0.5))
    br = gaze_data.get("bottom_right", (0.5, 0.5))

    # X калибровка
    gaze_x_left = (tl[0] + bl[0]) / 2.0
    gaze_x_right = (tr[0] + br[0]) / 2.0

    if abs(gaze_x_right - gaze_x_left) < 0.01:
        gaze_x_right = gaze_x_left + 0.1 # Защита от деления на 0

    scale_x = (1820 - 100) / (gaze_x_right - gaze_x_left)
    offset_x = 100 - scale_x * gaze_x_left

    # Y калибровка
    gaze_y_top = (tl[1] + tr[1]) / 2.0
    gaze_y_bottom = (bl[1] + br[1]) / 2.0

    if abs(gaze_y_bottom - gaze_y_top) < 0.01:
        gaze_y_bottom = gaze_y_top + 0.1

    scale_y = (980 - 100) / (gaze_y_bottom - gaze_y_top)
    offset_y = 100 - scale_y * gaze_y_top

    # === ЗАЩИТА ОТ ИНВЕРСИИ Y ===
    if scale_y < 0:
        print("[API] WARNING: Инверсия Y, исправляю")
        scale_y = 1500
        offset_y = SCREEN_HEIGHT / 2 - 0.5 * scale_y

    if scale_y > 3000:
        print(f"[API] WARNING: scale_y слишком большой ({scale_y:.2f}), ограничиваю")
        scale_y = 3000
        offset_y = SCREEN_HEIGHT / 2 - 0.5 * scale_y

    return {
        "scale_x": scale_x, "offset_x": offset_x,
        "scale_y": scale_y, "offset_y": offset_y
    }

def apply_calibration(gaze_points_raw: List[tuple], calibration: Dict[str, float]) -> List[tuple]:
    """Применяет калибровку к сырым точкам и ограничивает их экраном."""
    calibrated = []
    for gx, gy, ts in gaze_points_raw:
        px = gx * calibration["scale_x"] + calibration["offset_x"]
        py = gy * calibration["scale_y"] + calibration["offset_y"]

        px = max(0, min(SCREEN_WIDTH, px))
        py = max(0, min(SCREEN_HEIGHT, py))

        calibrated.append((px, py, ts))
    return calibrated

def save_token_to_db(token: str):
    """Сохраняет токен в PostgreSQL."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        now = datetime.now()
        expires = now + timedelta(minutes=5)

        cur.execute(
            "INSERT INTO captcha_tokens (token, is_used, created_at, expires_at) VALUES (%s, FALSE, %s, %s)",
            (token, now, expires)
        )
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DB] Token {token} saved successfully.")
    except Exception as e:
        print(f"[DB ERROR] Failed to save token: {e}")
        raise HTTPException(status_code=500, detail="Database error")

# === ЭНДПОИНТЫ ===

@app.post("/api/calibrate")
def calibrate_endpoint(req: CalibrateRequest):
    print("[API] Starting calibration...")
    gaze_data = {}

    # Обрабатываем каждую цель калибровки
    for target_name, frames_b64 in req.frames_by_target.items():
        gazes = []
        for b64 in frames_b64:
            img = decode_base64_image(b64)
            gaze = get_gaze_from_frame(img)
            if gaze:
                gazes.append(gaze)

        if gazes:
            # Берем среднее значение gaze для этой точки
            avg_x = sum(g[0] for g in gazes) / len(gazes)
            avg_y = sum(g[1] for g in gazes) / len(gazes)
            gaze_data[target_name] = (avg_x, avg_y)
            print(f"[API] Target {target_name}: avg gaze = ({avg_x:.3f}, {avg_y:.3f})")

    if len(gaze_data) < 2:
        raise HTTPException(status_code=400, detail="Not enough face data for calibration")

    calibration = calculate_calibration(gaze_data)
    session_id = str(uuid.uuid4())

    # Сохраняем калибровку в память
    active_sessions[session_id] = {
        "calibration": calibration,
        "created_at": time.time()
    }

    print(f"[API] Calibration done. Session: {session_id}")
    return {"success": True, "session_id": session_id}


@app.post("/api/verify")
def verify_endpoint(req: VerifyRequest):
    print(f"[API] Verifying session {req.session_id}...")

    if req.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    session = active_sessions[req.session_id]
    calibration = session["calibration"]

    all_scores = []
    all_details = []
    all_trajectories = []

    # Обрабатываем каждый стимул
    for target_name in req.sequence:
        frames_b64 = req.frames_by_target.get(target_name, [])
        if not frames_b64:
            all_scores.append(0.0)
            all_details.append({"error": "no_frames"})
            all_trajectories.append({"points": [], "target_x": 960, "target_y": 540})
            continue

        target_x, target_y = TARGET_COORDS.get(target_name, (960, 540))

        # === БУФЕР СГЛАЖИВАНИЯ ===
        smoothing_buffer = []
        SMOOTHING_WINDOW = 5  # Усредняем последние 5 кадров

        raw_gaze_points = []
        stimulus_time = time.time()

        for b64 in frames_b64:
            img = decode_base64_image(b64)
            gaze = get_gaze_from_frame(img)
            if gaze:
                # Добавляем сырую точку в буфер
                smoothing_buffer.append((gaze[0], gaze[1]))

                # Пока буфер не заполнен — пропускаем (ждём стабильности)
                if len(smoothing_buffer) < SMOOTHING_WINDOW:
                    continue

                # Усредняем последние N точек
                recent = smoothing_buffer[-SMOOTHING_WINDOW:]
                avg_x = sum(p[0] for p in recent) / len(recent)
                avg_y = sum(p[1] for p in recent) / len(recent)

                # Добавляем сглаженную точку
                raw_gaze_points.append((avg_x, avg_y, time.time()))

        # Применяем калибровку к сглаженным точкам
        calibrated_points = apply_calibration(raw_gaze_points, calibration)

        if len(calibrated_points) < 5:
            all_scores.append(0.0)
            all_details.append({"error": "not_enough_points"})
            all_trajectories.append({"points": [], "target_x": target_x, "target_y": target_y})
            continue

        # Считаем скор через анализатор
        score, details = score_stimulus(calibrated_points, target_x, target_y, stimulus_time)
        all_scores.append(score)

        # Сохраняем детали и траекторию
        all_details.append(details)
        trajectory = [
            {"x": round(p[0], 1), "y": round(p[1], 1), "t": round(p[2], 3)}
            for p in calibrated_points
        ]
        all_trajectories.append({
            "points": trajectory,
            "target_x": target_x,
            "target_y": target_y
        })

        print(f"[API] Stimulus {target_name} score: {score:.3f} (points: {len(calibrated_points)})")

    # Итоговый скор (среднее)
    final_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    print(f"[API] Final score: {final_score:.3f}")

    # Вычисляем статистику
    import statistics
    if len(all_scores) > 1:
        stats = {
            "mean": round(final_score, 3),
            "stdev": round(statistics.stdev(all_scores), 3),
            "count": len(all_scores)
        }
    else:
        stats = {
            "mean": round(final_score, 3),
            "stdev": 0.0,
            "count": len(all_scores)
        }

    # Удаляем сессию из памяти
    del active_sessions[req.session_id]

    if final_score >= SESSION_THRESHOLD:
        token = str(uuid.uuid4())
        save_token_to_db(token)
        return {
            "success": True,
            "token": token,
            "score": round(final_score, 3),
            "stimuli": [round(s, 3) for s in all_scores],
            "details": all_details,
            "trajectories": all_trajectories,
            "stats": stats,
            "sequence": req.sequence,
            "threshold": SESSION_THRESHOLD
        }
    else:
        return {
            "success": False,
            "error": f"Score too low: {final_score:.3f}",
            "score": round(final_score, 3),
            "stimuli": [round(s, 3) for s in all_scores],
            "details": all_details,
            "trajectories": all_trajectories,
            "stats": stats,
            "sequence": req.sequence,
            "threshold": SESSION_THRESHOLD
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
