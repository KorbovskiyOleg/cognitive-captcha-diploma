from dataclasses import dataclass


@dataclass
class VelocityValidationResult:
    is_valid: bool
    reason: str
    details: dict


def validate_velocity(profile, min_points: int = 10):
    """
    Проверка правдоподобия движения глаз по velocity-профилю.

    Порог пиков теперь динамический: ~1 пик на 4 точки.
    """
    mean_v = profile.mean_velocity
    max_v = profile.max_velocity
    peaks = profile.peak_count
    num_points = getattr(profile, 'num_points', 0)

    # Проверка минимального количества точек
    if num_points > 0 and num_points < min_points:
        return VelocityValidationResult(
            is_valid=False,
            reason="insufficient_data",
            details={"num_points": num_points, "min_required": min_points}
        )

    ratio = max_v / mean_v if mean_v > 0 else 0

    # Слишком ровное движение (бот)
    if ratio < 1.5:
        return VelocityValidationResult(
            is_valid=False,
            reason="velocity_too_uniform",
            details={"ratio": ratio}
        )

    # Нет саккад
    if peaks == 0:
        return VelocityValidationResult(
            is_valid=False,
            reason="no_saccades_detected",
            details={"peaks": peaks}
        )

    # ДИНАМИЧЕСКИЙ ПОРОГ: 1 пик на 3 точки (было фиксированное 15)
    # Для 57 точек порог = 19, для 30 точек порог = 10
    dynamic_threshold = max(15, num_points // 3) if num_points > 0 else 20

    if peaks > dynamic_threshold:
        return VelocityValidationResult(
            is_valid=False,
            reason="too_many_velocity_peaks",
            details={
                "peaks": peaks,
                "threshold": dynamic_threshold,
                "num_points": num_points
            }
        )

    return VelocityValidationResult(
        is_valid=True,
        reason="ok",
        details={
            "ratio": ratio,
            "peaks": peaks,
            "threshold": dynamic_threshold
        }
    )