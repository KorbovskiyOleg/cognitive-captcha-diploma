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
    """
    if len(gaze_points) < 2:
        return 180.0

    x0, y0, _ = gaze_points[0]
    x1, y1, _ = gaze_points[-1]

    dx_movement = x1 - x0
    dx_target = target_x - x0

    if abs(dx_movement) < 1:
        return 180.0

    if (dx_movement > 0 and dx_target > 0) or (dx_movement < 0 and dx_target < 0):
        return 0.0

    return 180.0

def angle_score(angle_error):
    return max(0.0, 1 - angle_error / 90)

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

