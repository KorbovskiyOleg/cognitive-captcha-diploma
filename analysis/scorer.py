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

# Евлкидово расстояние
def euclidean_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

# проверяем, точка внутри рамки(основа для штрафов)
def is_inside_bounds(x, y, target_x, target_y):
    half_w = config.BOUND_BOX_WIDTH / 2
    half_h = config.BOUND_BOX_HEIGHT / 2

    return (
            target_x - half_w <= x <= target_x + half_w and
            target_y - half_h <= y <= target_y + half_h
    )


#=======================================================================================
#                             Признак №1 - Latancy(задержка реакции)
#=========================================================================================
def compute_latency(
        gaze_points,
        stimulus_time,
        min_step=6,          # минимальный шаг между точками
        min_steps_count=3,   # сколько подряд шагов
        total_threshold=20   # суммарное движение
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

# нормализация latency - score
def latency_score(latency):
    if latency is None:
        return 0.0

    # слишком быстро — не человек
    if latency < config.MIN_LATENCY:
        return 0.0

    # оптимальная зона
    if latency <= config.OPT_LATENCY:
        return 1.0

    # медленно — линейное падение
    if latency <= config.MAX_LATENCY:
        return 1 - (latency - config.OPT_LATENCY) / (
                config.MAX_LATENCY - config.OPT_LATENCY
        )

    return 0.0

#============================================================================================
#                                  Приизнак №2 - Distance error(средняя ошибка расстояния)
#============================================================================================
def compute_distance_error(gaze_points, target_x, target_y):
    distances = [
        euclidean_distance(x, y, target_x, target_y)
        for x, y, _ in gaze_points
    ]
    return sum(distances) / len(distances)

# нормализация
def distance_score(distance_error):
    max_dist = math.sqrt(config.SCREEN_WIDTH**2 + config.SCREEN_HEIGHT**2)
    score = 1 - (distance_error / max_dist)
    return max(0.0, min(score, 1.0))

#===============================================================================================
#                                 Признак №3 - Out ratio(выход за рамки)
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

# score
def bounds_score(out_ratio):
    return 1 - out_ratio

#==================================================================================================
#                           Признак №4 - Angle error(направление движения)
#==================================================================================================
def compute_angle_error(gaze_points, target_x, target_y):
    if len(gaze_points) < 2:
        return 180.0

    x0, y0, _ = gaze_points[0]
    x1, y1, _ = gaze_points[-1]

    v1 = (x1 - x0, y1 - y0)
    v2 = (target_x - x0, target_y - y0)

    dot = v1[0]*v2[0] + v1[1]*v2[1]
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)

    if mag1 == 0 or mag2 == 0:
        return 180.0

    cos_angle = max(-1.0, min(dot / (mag1 * mag2), 1.0))
    angle = math.degrees(math.acos(cos_angle))

    return angle

# score
def angle_score(angle_error):
    return max(0.0, 1 - angle_error / 90)

#======================================================================================================
#                               Общий score для одного стимула
#=======================================================================================================
def score_stimulus(gaze_points, target_x, target_y, stimulus_time):
    latency = compute_latency(gaze_points,stimulus_time)
    distance_err = compute_distance_error(gaze_points, target_x, target_y)
    angle_err = compute_angle_error(gaze_points, target_x, target_y)
    out_ratio = compute_out_of_bounds_ratio(
        gaze_points, target_x, target_y, stimulus_time
    )

    scores = {
        "latency": latency_score(latency),
        "distance_error": distance_score(distance_err),
        "angle_error": angle_score(angle_err),
        "out_of_bounds_ratio": bounds_score(out_ratio),
    }

    total = sum(
        scores[k] * config.FEATURE_WEIGHTS[k]
        for k in scores
    )

    return total, scores

