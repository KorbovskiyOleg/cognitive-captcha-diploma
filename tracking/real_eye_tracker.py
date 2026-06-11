"""
Реальный eye-tracker с вычислением направления взгляда через iris.
Со сглаживанием и высоким разрешением.
"""

import cv2
import mediapipe as mp
import threading
import queue
import time
import config
from typing import List, Tuple, Callable, Optional, Deque
from collections import deque
import numpy as np


class RealEyeTracker:
    """
    Собирает точки взгляда через вычисление направления взгляда.
    Применяет скользящее среднее для сглаживания шума.
    """

    LEFT_IRIS_CENTER = 468
    RIGHT_IRIS_CENTER = 473

    LEFT_EYE_LEFT = 33
    LEFT_EYE_RIGHT = 133
    LEFT_EYE_TOP = 159
    LEFT_EYE_BOTTOM = 145

    RIGHT_EYE_LEFT = 362
    RIGHT_EYE_RIGHT = 263
    RIGHT_EYE_TOP = 386
    RIGHT_EYE_BOTTOM = 374

    # Размер окна сглаживания (усредняем последние N точек)
    SMOOTHING_WINDOW = 9

    def __init__(
            self,
            camera_index: int = 0,
            fps: int = 30,
            gui_update_callback: Optional[Callable] = None
    ):
        self.camera_index = camera_index
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self.gui_update_callback = gui_update_callback

        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.cap: cv2.VideoCapture = None
        self._thread: threading.Thread = None
        self._stop_event = threading.Event()
        self._points_queue: queue.Queue = queue.Queue()
        self._running = False
        self._last_frame_time = 0.0
        self._frame_count = 0

        # Буфер для сглаживания (последние N сырых точек)
        self._smoothing_buffer: Deque[Tuple[float, float]] = deque(
            maxlen=self.SMOOTHING_WINDOW
        )

        # Калибровочные коэффициенты
        self.calibration = {
            "scale_x": config.SCREEN_WIDTH,
            "scale_y": config.SCREEN_HEIGHT,
            "offset_x": 0.0,
            "offset_y": 0.0
        }

    def start(self):
        """Публичный метод запуска камеры."""
        if not self._running:
            self._start_camera()

    def set_calibration(self, calibration_data: dict):
            """Устанавливает калибровочные коэффициенты с защитой от инверсии."""
            scale_x = calibration_data.get("scale_x", config.SCREEN_WIDTH)
            scale_y = calibration_data.get("scale_y", config.SCREEN_HEIGHT)
            offset_x = calibration_data.get("offset_x", 0.0)
            offset_y = calibration_data.get("offset_y", 0.0)

        # Защита от инверсии Y
            if scale_y < 0:
                print(f"[RealEyeTracker] WARNING: Инверсия Y обнаружена (scale_y={scale_y:.2f}), исправляю")
                scale_y = 1500  # Используем разумное значение по умолчанию
                offset_y = 0  # Начало координат в левом верхнем углу

        # Ограничение максимального scale_y
            if scale_y > 3000:
                print(f"[RealEyeTracker] WARNING: scale_y слишком большой ({scale_y:.2f}), ограничиваю до 3000")
                scale_y = 3000
                offset_y = 0

            self.calibration = {
                "scale_x": scale_x,
                "scale_y": scale_y,
                "offset_x": offset_x,
                "offset_y": offset_y
            }

            print(f"[RealEyeTracker] Калибровка установлена: "
                    f"scale=({self.calibration['scale_x']:.2f}, {self.calibration['scale_y']:.2f}), "
                    f"offset=({self.calibration['offset_x']:.2f}, {self.calibration['offset_y']:.2f})")

    def get_recent_gaze_samples(self, duration: float = 2.0) -> List[Tuple[float, float]]:
        """
        Возвращает образцы gaze за последние duration секунд.
        Используется во время калибровки.
        """
        samples = []
        cutoff_time = time.time() - duration

        temp_points = []
        while not self._points_queue.empty():
            try:
                point = self._points_queue.get_nowait()
                temp_points.append(point)
            except queue.Empty:
                break

        for norm_x, norm_y, ts in temp_points:
            if ts >= cutoff_time:
                samples.append((norm_x, norm_y))
                self._points_queue.put((norm_x, norm_y, ts))

        return samples

    def collect(
            self,
            start_time: float,
            duration: float,
            target: Tuple[float, float]
    ) -> List[Tuple[float, float, float]]:
        """
        Собирает точки взгляда в течение duration секунд.
        Применяет калибровку для перевода gaze → screen coordinates.
        """
        if not self._running:
            self._start_camera()

        self._clear_queue()
        self._smoothing_buffer.clear()

        gaze_points = []
        end_time = start_time + duration

        print(f"\n[RealEyeTracker] Сбор точек: {duration:.1f}с, target={target}")

        while time.time() < end_time:
            try:
                norm_x, norm_y, ts = self._points_queue.get(
                    timeout=self.frame_interval * 2
                )

                if ts < start_time - 0.1:
                    continue

                # Сглаживание: добавляем в буфер и берём среднее
                self._smoothing_buffer.append((norm_x, norm_y))
                if len(self._smoothing_buffer) < self.SMOOTHING_WINDOW:
                    # Пока буфер не заполнен — пропускаем (ждём стабильности)
                    continue

                avg_x = sum(p[0] for p in self._smoothing_buffer) / len(self._smoothing_buffer)
                avg_y = sum(p[1] for p in self._smoothing_buffer) / len(self._smoothing_buffer)

                # Применяем калибровку
                pixel_x = avg_x * self.calibration["scale_x"] + self.calibration["offset_x"]
                pixel_y = avg_y * self.calibration["scale_y"] + self.calibration["offset_y"]

                # Ограничиваем координаты пределами экрана
                pixel_x = np.clip(pixel_x, 0, config.SCREEN_WIDTH)
                pixel_y = np.clip(pixel_y, 0, config.SCREEN_HEIGHT)

                gaze_points.append((pixel_x, pixel_y, ts))

            except queue.Empty:
                pass

            if self.gui_update_callback:
                self.gui_update_callback()

        print(f"[RealEyeTracker] Собрано {len(gaze_points)} точек (со сглаживанием window={self.SMOOTHING_WINDOW}).")

        if len(gaze_points) > 0:
            for i, (x, y, t) in enumerate(gaze_points[:10]):
                print(f"  {i:02d}: x={x:.1f}, y={y:.1f}, t={t:.3f}")
            if len(gaze_points) > 10:
                print(f"  ... и ещё {len(gaze_points) - 10}")

        return gaze_points

    def stop(self):
        """Остановка камеры."""
        if self._running:
            self._running = False
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=3.0)
            if self.cap:
                self.cap.release()
                self.cap = None
            print("[RealEyeTracker] Камера остановлена.")

    def _start_camera(self):
        """Запуск камеры и потока сбора."""
        print(f"[RealEyeTracker] Открываю камеру #{self.camera_index}...")

        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Не удалось открыть камеру #{self.camera_index}")

        # УВЕЛИЧЕННОЕ РАЗРЕШЕНИЕ для более точного трекинга iris
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"[RealEyeTracker] Разрешение камеры: {actual_w}x{actual_h}")

        time.sleep(1.0)

        for _ in range(5):
            ret, frame = self.cap.read()
            if ret:
                break
            time.sleep(0.1)

        self._stop_event.clear()
        self._running = True
        self._frame_count = 0
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[RealEyeTracker] Камера запущена.")
        time.sleep(0.5)

    def _capture_loop(self):
        """Основной цикл потока захвата."""
        while self._running and not self._stop_event.is_set():
            now = time.perf_counter()
            if now - self._last_frame_time < self.frame_interval:
                time.sleep(0.001)
                continue

            ret, frame = self.cap.read()
            if not ret:
                continue

            self._last_frame_time = now
            self._frame_count += 1
            self._process_frame(frame, time.time())

    def _process_frame(self, frame, timestamp: float):
        """Обработка кадра: вычисление направления взгляда."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.face_mesh.process(rgb)
        rgb.flags.writeable = True

        if not results.multi_face_landmarks:
            return

        landmarks = results.multi_face_landmarks[0].landmark
        h, w, _ = frame.shape

        gaze_x, gaze_y = self._compute_gaze_direction(landmarks, w, h)

        gaze_x = 1.0 - gaze_x

        if self._frame_count <= 10:
            print(f"[DEBUG] Кадр #{self._frame_count}: gaze=({gaze_x:.3f}, {gaze_y:.3f})")

        self._points_queue.put((gaze_x, gaze_y, timestamp))

    def _compute_gaze_direction(self, landmarks, frame_w, frame_h) -> Tuple[float, float]:
        """
        Вычисляет направление взгляда через позицию iris относительно глаза.
        """
        # Левый глаз
        left_iris = landmarks[self.LEFT_IRIS_CENTER]
        left_eye_left = landmarks[self.LEFT_EYE_LEFT]
        left_eye_right = landmarks[self.LEFT_EYE_RIGHT]
        left_eye_top = landmarks[self.LEFT_EYE_TOP]
        left_eye_bottom = landmarks[self.LEFT_EYE_BOTTOM]

        iris_x = left_iris.x * frame_w
        iris_y = left_iris.y * frame_h

        eye_width = abs(left_eye_right.x - left_eye_left.x) * frame_w
        eye_height = abs(left_eye_bottom.y - left_eye_top.y) * frame_h

        eye_center_x = (left_eye_left.x + left_eye_right.x) / 2.0 * frame_w
        eye_center_y = (left_eye_top.y + left_eye_bottom.y) / 2.0 * frame_h

        ratio_x = (iris_x - eye_center_x) / (eye_width / 2.0)
        ratio_y = (iris_y - eye_center_y) / (eye_height / 2.0)

        # Правый глаз
        right_iris = landmarks[self.RIGHT_IRIS_CENTER]
        right_eye_left = landmarks[self.RIGHT_EYE_LEFT]
        right_eye_right = landmarks[self.RIGHT_EYE_RIGHT]
        right_eye_top = landmarks[self.RIGHT_EYE_TOP]
        right_eye_bottom = landmarks[self.RIGHT_EYE_BOTTOM]

        right_iris_x = right_iris.x * frame_w
        right_iris_y = right_iris.y * frame_h

        right_eye_width = abs(right_eye_right.x - right_eye_left.x) * frame_w
        right_eye_height = abs(right_eye_bottom.y - right_eye_top.y) * frame_h

        right_eye_center_x = (right_eye_left.x + right_eye_right.x) / 2.0 * frame_w
        right_eye_center_y = (right_eye_top.y + right_eye_bottom.y) / 2.0 * frame_h

        right_ratio_x = (right_iris_x - right_eye_center_x) / (right_eye_width / 2.0)
        right_ratio_y = (right_iris_y - right_eye_center_y) / (right_eye_height / 2.0)

        avg_ratio_x = (ratio_x + right_ratio_x) / 2.0
        avg_ratio_y = (ratio_y + right_ratio_y) / 2.0

        if self._frame_count <= 10:
            print(f"[DEBUG] ratio_x={avg_ratio_x:.3f}, ratio_y={avg_ratio_y:.3f}, "
                  f"eye_w={eye_width:.1f}, eye_h={eye_height:.1f}")

        gaze_x = np.clip((avg_ratio_x + 1.0) / 2.0, 0.0, 1.0)
        gaze_y = np.clip((avg_ratio_y + 1.0) / 2.0, 0.0, 1.0)

        return gaze_x, gaze_y

    def _clear_queue(self):
        """Очистка очереди точек."""
        while not self._points_queue.empty():
            try:
                self._points_queue.get_nowait()
            except queue.Empty:
                break