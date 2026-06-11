"""
Eye-tracker на базе GazeTracking (более точный чем MediaPipe Iris).
Drop-in замена: тот же интерфейс что у RealEyeTracker.
"""

from gaze_tracking import GazeTracking
import threading
import queue
import time
import config
from typing import List, Tuple, Callable, Optional, Deque
from collections import deque
import numpy as np
import cv2


class RealEyeTracker:
    """
    Собирает точки взгляда через GazeTracking.
    Применяет скользящее среднее для сглаживания шума.
    """

    # Размер окна сглаживания
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

        # Инициализация GazeTracking
        self.gaze = GazeTracking()

        self._thread: threading.Thread = None
        self._stop_event = threading.Event()
        self._points_queue: queue.Queue = queue.Queue()
        self._running = False
        self._last_frame_time = 0.0
        self._frame_count = 0

        # Буфер для сглаживания
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
            print(f"[RealEyeTracker] WARNING: Инверсия Y (scale_y={scale_y:.2f}), исправляю")
            scale_y = 1500
            offset_y = config.SCREEN_HEIGHT / 2 - 0.5 * scale_y

        # Ограничение максимального scale_y с пересчётом offset
        if scale_y > 3000:
            print(f"[RealEyeTracker] WARNING: scale_y слишком большой ({scale_y:.2f}), ограничиваю")
            scale_y = 3000
            offset_y = config.SCREEN_HEIGHT / 2 - 0.5 * scale_y
            print(f"[RealEyeTracker] offset_y пересчитан: {offset_y:.2f}")

        # Ограничение scale_x
        if scale_x > 10000:
            print(f"[RealEyeTracker] WARNING: scale_x слишком большой ({scale_x:.2f}), ограничиваю")
            scale_x = 8000
            offset_x = config.SCREEN_WIDTH / 2 - 0.5 * scale_x

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
        """Возвращает образцы gaze за последние duration секунд."""
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

                # Сглаживание
                self._smoothing_buffer.append((norm_x, norm_y))
                if len(self._smoothing_buffer) < self.SMOOTHING_WINDOW:
                    continue

                avg_x = sum(p[0] for p in self._smoothing_buffer) / len(self._smoothing_buffer)
                avg_y = sum(p[1] for p in self._smoothing_buffer) / len(self._smoothing_buffer)

                # Применяем калибровку
                pixel_x = avg_x * self.calibration["scale_x"] + self.calibration["offset_x"]
                pixel_y = avg_y * self.calibration["scale_y"] + self.calibration["offset_y"]

                # Ограничиваем пределами экрана
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
            # GazeTracking освобождает камеру автоматически при выходе
            print("[RealEyeTracker] Камера остановлена.")

    def _start_camera(self):
        """Запуск камеры и потока сбора."""
        print(f"[RealEyeTracker] Запускаю GazeTracking на камере #{self.camera_index}...")

        # GazeTracking сам открывает камеру, но нужно настроить индекс
        # К сожалению, GazeTracking не даёт прямого API для индекса камеры,
        # но обычно использует камеру 0
        if self.camera_index != 0:
            print(f"[RealEyeTracker] WARNING: GazeTracking обычно использует камеру 0")

        # Прогрев: читаем несколько кадров
        for _ in range(5):
            try:
                # Временно используем cv2 для прогрева
                cap = cv2.VideoCapture(self.camera_index)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        break
            except:
                pass
            time.sleep(0.1)

        self._stop_event.clear()
        self._running = True
        self._frame_count = 0
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[RealEyeTracker] GazeTracking запущен.")
        time.sleep(0.5)

    def _capture_loop(self):
        """Основной цикл потока захвата."""
        while self._running and not self._stop_event.is_set():
            now = time.perf_counter()
            if now - self._last_frame_time < self.frame_interval:
                time.sleep(0.001)
                continue

            # Читаем кадр через cv2
            if not hasattr(self, '_cap') or not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.camera_index)
                if not self._cap.isOpened():
                    time.sleep(0.1)
                    continue

            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            self._last_frame_time = now
            self._frame_count += 1
            self._process_frame(frame, time.time())

    def _process_frame(self, frame, timestamp: float):
        """Обработка кадра через GazeTracking."""
        # Передаём кадр в GazeTracking
        self.gaze.refresh(frame)

        # Получаем ratios
        h_ratio = self.gaze.horizontal_ratio()
        v_ratio = self.gaze.vertical_ratio()

        # Если GazeTracking не смог определить взгляд
        if h_ratio is None or v_ratio is None:
            return

        # Нормализуем: h_ratio обычно 0-1, v_ratio 0-1
        # Но GazeTracking может давать другие диапазоны,
        # поэтому clip в разумные пределы
        gaze_x = np.clip(h_ratio, 0.0, 1.0)
        gaze_y = np.clip(v_ratio, 0.0, 1.0)

        if self._frame_count <= 10:
            print(f"[DEBUG] Кадр #{self._frame_count}: gaze=({gaze_x:.3f}, {gaze_y:.3f})")

        self._points_queue.put((gaze_x, gaze_y, timestamp))

    def _clear_queue(self):
        """Очистка очереди точек."""
        while not self._points_queue.empty():
            try:
                self._points_queue.get_nowait()
            except queue.Empty:
                break