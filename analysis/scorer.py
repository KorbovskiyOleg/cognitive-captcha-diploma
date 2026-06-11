# интеллект системы

# вычисление признаков
# штрафы
# локальный score стимула
# агрегирование

# алгоритмическое ядро
#
#
import math
from typing import Tuple

import config

# тип точки взгляда
GazePoint = Tuple[float, float, float]  # (x, y, t)

# Евклидово расстояние ТОЛЬКО ПО X (Y отключён)
def euclidean_distance(x1, y1, x2, y2):
    return abs(x2 - x1)

# проверяем, точка внутри рамки ТОЛЬКО ПО X (Y отключён)
def is_inside_bounds(x, y, target_x, target_y):
    half_w = config.BOUND_BOX_WIDTH / 2
    return target_x - half_w <= x <= target_x + half_w


#=======================================================================================
#                             Признак №1 - Latency(задержка реакции)
#=========================================================================================
def compute_latency(
        gaze_points,
        stimulus_time,
        min_step=6,
        min_steps_count=3,
        total_threshold=20
):
    if len(gaze_points) < min_steps_count + 1:
        return None

    consecutive_steps = 0
    total_movement = 0.0

    prev_x, prev_y, _ = gaze_points[0]

    for x, y, t in gaze_points[1:]:
        step = math.hypot(x - prev_x, y - prev_y)

        if step >= min_step:
            consecutive_steps += 1
            total_movement += step
        else:
            consecutive_steps = 0
            total_movement = 0.0

        if consecutive_steps >= min_steps_count and total_movement >= total_threshold:
            return t - stimulus_time

        prev_x, prev_y = x, y

    return None

def latency_score(latency):
    if latency is None:
        return 0.0

    if latency < config.MIN_LATENCY:
        return 0.0

    if latency <= config.OPT_LATENCY:
        return 1.0

    if latency <= config.MAX_LATENCY:
        return 1 - (latency - config.OPT_LATENCY) / (
                config.MAX_LATENCY - config.OPT_LATENCY
        )

    return 0.0

#============================================================================================
#                                  Признак №2 - Distance error (ТОЛЬКО ПО X)
#============================================================================================
def compute_distance_error(gaze_points, target_x, target_y):
    distances = [
        euclidean_distance(x, y, target_x, target_y)
        for x, y, _ in gaze_points
    ]
    return sum(distances) / len(distances)

def distance_score(distance_error):
    # Максимальная ошибка теперь только по X (ширина экрана)
    max_dist = config.SCREEN_WIDTH
    score = 1 - (distance_error / max_dist)
    return max(0.0, min(score, 1.0))

#===============================================================================================
#                                 Признак №3 - Out ratio (ТОЛЬКО ПО X)
#===============================================================================================
def compute_out_of_bounds_ratio(gaze_points, target_x, target_y, stimulus_time):
    valid_points = [
        (x, y, t) for x, y, t in gaze_points
        if t - stimulus_time >= config.LATENCY_WINDOW
    ]

    if not valid_points:
        return 1.0

    out_count = sum(
        not is_inside_bounds(x, y, target_x, target_y)
        for x, y, _ in valid_points
    )

    return out_count / len(valid_points)

def bounds_score(out_ratio):
    return 1 - out_ratio

#==================================================================================================
#                           Признак №4 - Angle error (ТОЛЬКО ПО X)
#==================================================================================================
def compute_angle_error(gaze_points, target_x, target_y):
    """
    Считает угол направления движения ТОЛЬКО ПО ГОРИЗОНТАЛИ.
    Возвращает угол от 0° (идеально) до 180° (противоположно).
    """
    if len(gaze_points) < 2:
        return 180.0

    x0, y0, _ = gaze_points[0]
    x1, y1, _ = gaze_points[-1]

    dx_movement = x1 - x0
    dx_target = target_x - x0

    if abs(dx_movement) < 1:
        return 180.0

    # Вычисляем насколько направление совпадает (0 = идеально, 1 = противоположно)
    # Если оба в одну сторону — ratio положительный
    # Если в разные стороны — ratio отрицательный
    if abs(dx_target) < 1:
        return 0.0  # target прямо перед нами

    ratio = (dx_movement / abs(dx_movement)) * (dx_target / abs(dx_target))

    # ratio = 1 → идеальное совпадение → угол 0°
    # ratio = -1 → противоположно → угол 180°
    # ratio = 0.5 → частичное совпадение → угол ~60°

    if ratio >= 1.0:
        return 0.0
    elif ratio <= -1.0:
        return 180.0
    else:
        # Линейная интерполяция: ratio от -1 до 1 → угол от 180° до 0°
        return (1 - ratio) * 90.0  # ratio=1 → 0°, ratio=-1 → 180°, ratio=0 → 90°

def angle_score(angle_error):
    return max(0.0, 1 - angle_error / 90)


#==================================================================================================
#                           Признак №5 - Dispersion (разброс точек)
#==================================================================================================
def compute_dispersion(gaze_points):
    """
    Считает средний разброс точек (стандартное отклонение) по X.
    Высокий разброс = хаотичные движения.
    """
    if len(gaze_points) < 2:
        return 0.0

    x_coords = [p[0] for p in gaze_points]
    mean_x = sum(x_coords) / len(x_coords)
    variance = sum((x - mean_x) ** 2 for x in x_coords) / len(x_coords)
    std_dev = variance ** 0.5

    return std_dev

def dispersion_score(dispersion):
    """
    Нормализация: низкий разброс = высокий score.
    """
    # Максимальный разброс = ширина экрана
    max_dispersion = config.SCREEN_WIDTH / 2  # 960 пикселей
    score = 1 - (dispersion / max_dispersion)
    return max(0.0, min(score, 1.0))

#======================================================================================================
#                               Общий score для одного стимула
#=======================================================================================================
def score_stimulus(gaze_points, target_x, target_y, stimulus_time):
    latency = compute_latency(gaze_points, stimulus_time)
    distance_err = compute_distance_error(gaze_points, target_x, target_y)
    angle_err = compute_angle_error(gaze_points, target_x, target_y)
    out_ratio = compute_out_of_bounds_ratio(
        gaze_points, target_x, target_y, stimulus_time
    )
    dispersion = compute_dispersion(gaze_points)

    scores = {
        "latency": latency_score(latency),
        "distance_error": distance_score(distance_err),
        "angle_error": angle_score(angle_err),
        "out_of_bounds_ratio": bounds_score(out_ratio),
        "dispersion": dispersion_score(dispersion),
    }

    total = sum(
        scores[k] * config.FEATURE_WEIGHTS[k]
        for k in scores
    )

    return total, scores

