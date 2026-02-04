# для двух соседних точек (x1,y1,t1)->(x2,y2,t2) скорость v = distance / Δt
# где distance = sqrt((x2-x1)² + (y2-y1)²)
# Δt = t2 - t1
# это мгновенная скорость взгляда между двумя измерениями

# analysis/dynamics/velocity.py
import math
from dataclasses import dataclass


@dataclass
class VelocityProfile:
    velocities: list
    times: list
    mean_velocity: float
    max_velocity: float
    peak_count: int


def compute_velocity_profile(gaze_points):
    """
    Строит профиль скорости по gaze-точкам
    gaze_points: [(x, y, t), ...]
    """

    if len(gaze_points) < 3:
        return None

    velocities = []
    times = []

    for i in range(1, len(gaze_points)):
        x1, y1, t1 = gaze_points[i - 1]
        x2, y2, t2 = gaze_points[i]

        dt = t2 - t1
        if dt <= 0:
            continue

        dist = math.hypot(x2 - x1, y2 - y1)
        v = dist / dt

        velocities.append(v)
        times.append(t2)

    if not velocities:
        return None

    mean_v = sum(velocities) / len(velocities)
    max_v = max(velocities)

    # считаем пики (простейшая эвристика)
    peak_count = 0
    for i in range(1, len(velocities) - 1):
        if velocities[i] > velocities[i - 1] and velocities[i] > velocities[i + 1]:
            peak_count += 1

    return VelocityProfile(
        velocities=velocities,
        times=times,
        mean_velocity=mean_v,
        max_velocity=max_v,
        peak_count=peak_count
    )
