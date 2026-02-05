from dataclasses import dataclass


@dataclass
class VelocityValidationResult:
    is_valid: bool
    reason: str
    details: dict


def validate_velocity(profile):
    """
    Проверка правдоподобия движения глаз по velocity-профилю
    """

    mean_v = profile.mean_velocity
    max_v = profile.max_velocity
    peaks = profile.peak_count

    ratio = max_v / mean_v if mean_v > 0 else 0

    # Слишком ровное движение
    if ratio < 1.5:
        return VelocityValidationResult(
            is_valid=False,
            reason="velocity_too_uniform",
            details={"ratio": ratio}
        )

    #  Нет саккад
    if peaks == 0:
        return VelocityValidationResult(
            is_valid=False,
            reason="no_saccades_detected",
            details={"peaks": peaks}
        )

    # Слишком много рывков — шум
    if peaks > 8:
        return VelocityValidationResult(
            is_valid=False,
            reason="too_many_velocity_peaks",
            details={"peaks": peaks}
        )

    return VelocityValidationResult(
        is_valid=True,
        reason="ok",
        details={
            "ratio": ratio,
            "peaks": peaks
        }
    )
