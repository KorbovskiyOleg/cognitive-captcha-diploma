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
# ЗАМЕНИ НА СВОИ ДАННЫЕ ПОДКЛЮЧЕНИЯ К POSTGRESQL!
DB_CONFIG = {
    "dbname": "cardb",
    "user": "postgres",       # Твой пользователь БД
    "password": "karbit",   # Твой пароль БД
    "host": "localhost",
    "port": "5432"
}

# Размеры экрана (должны совпадать с JS и Java)
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
SESSION_THRESHOLD = 0.3

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
    """
    if frame is None:
        return None

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    if not results.multi_face_landmarks:
        return None

    landmarks = results.multi_face_landmarks[0].landmark

    # === ЛЕВЫЙ ГЛАЗ ===
    left_eye_inner = landmarks[133]
    left_eye_outer = landmarks[33]
    left_eye_top = landmarks[159]
    left_eye_bottom = landmarks[145]
    left_iris_center = landmarks[468]

    left_eye_width = abs(left_eye_outer.x - left_eye_inner.x)
    left_eye_height = abs(left_eye_top.y - left_eye_bottom.y)

    if left_eye_width < 0.001 or left_eye_height < 0.001:
        return None

    left_ratio_x = (left_iris_center.x - left_eye_inner.x) / left_eye_width
    left_ratio_y = (left_iris_center.y - left_eye_top.y) / left_eye_height

    # === ПРАВЫЙ ГЛАЗ ===
    right_eye_inner = landmarks[362]
    right_eye_outer = landmarks[263]
    right_eye_top = landmarks[386]
    right_eye_bottom = landmarks[374]
    right_iris_center = landmarks[473]

    right_eye_width = abs(right_eye_outer.x - right_eye_inner.x)
    right_eye_height = abs(right_eye_top.y - right_eye_bottom.y)

    if right_eye_width < 0.001 or right_eye_height < 0.001:
        return None

    right_ratio_x = (right_iris_center.x - right_eye_inner.x) / right_eye_width
    right_ratio_y = (right_iris_center.y - right_eye_top.y) / right_eye_height

    # === УСРЕДНЕНИЕ ===
    avg_ratio_x = (left_ratio_x + right_ratio_x) / 2.0
    avg_ratio_y = (left_ratio_y + right_ratio_y) / 2.0

    # === ОТЛАДКА ===
    print(f"  [DEBUG] raw: ratio_x={avg_ratio_x:.3f}, ratio_y={avg_ratio_y:.3f}")

    # === ПРАВИЛЬНАЯ НОРМАЛИЗАЦИЯ ===
    # ratio_x: от -0.15 (лево) до +0.15 (право) → gaze_x от 0 до 1
    gaze_x = (avg_ratio_x + 0.15) / 0.30
    gaze_x = max(0.0, min(1.0, gaze_x))

    # ratio_y: от 0.30 (верх) до 0.50 (низ) → gaze_y от 0 до 1
    gaze_y = (avg_ratio_y - 0.30) / 0.20
    gaze_y = max(0.0, min(1.0, gaze_y))

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

    # === ЗАЩИТА ОТ ИНВЕРСИИ Y (как в твоем десктопном приложении) ===
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

    # Обрабатываем каждый стимул
    for target_name in req.sequence:
        frames_b64 = req.frames_by_target.get(target_name, [])
        if not frames_b64:
            continue

        target_x, target_y = TARGET_COORDS.get(target_name, (960, 540))
        raw_gaze_points = []
        stimulus_time = time.time()

        for b64 in frames_b64:
            img = decode_base64_image(b64)
            gaze = get_gaze_from_frame(img)
            if gaze:
                raw_gaze_points.append((gaze[0], gaze[1], time.time()))

        # Применяем калибровку
        calibrated_points = apply_calibration(raw_gaze_points, calibration)

        if len(calibrated_points) < 5:
            all_scores.append(0.0)
            continue

        # Считаем скор через твой анализатор
        score, details = score_stimulus(calibrated_points, target_x, target_y, stimulus_time)
        all_scores.append(score)
        print(f"[API] Stimulus {target_name} score: {score:.3f}")

    # Итоговый скор (среднее)
    final_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    print(f"[API] Final score: {final_score:.3f}")

    # Удаляем сессию из памяти
    del active_sessions[req.session_id]

    if final_score >= SESSION_THRESHOLD:
        token = str(uuid.uuid4())
        save_token_to_db(token)
        return {"success": True, "token": token, "score": final_score}
    else:
        return {"success": False, "error": f"Score too low: {final_score:.3f}", "score": final_score}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)