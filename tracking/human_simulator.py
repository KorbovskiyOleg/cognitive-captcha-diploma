import random
import math
import config


class HumanLikeEyeTracker:
    """
    Синтетическая модель человеческого движения глаз
    """

    def __init__(
            self,
            reaction_delay_range=(0.2, 0.45),
            noise_level=25,
            points=25
    ):
        self.reaction_delay_range = reaction_delay_range
        self.noise_level = noise_level
        self.points = points

    def collect(self, start_time, duration, target=None):
        """
        Генерирует человекоподобную траекторию взгляда
        """

        # старт — центр экрана
        x_start = config.SCREEN_WIDTH / 2
        y_start = config.SCREEN_HEIGHT / 2

        # цель — если не передали, берём случайный угол
        if target is None:
            target = random.choice(list(config.CORNERS.values()))

        x_target, y_target = target

        # 1️⃣ Реакционная пауза
        reaction_delay = random.uniform(*self.reaction_delay_range)

        gaze_points = []
        t = start_time

        # взгляд стоит на месте
        gaze_points.append((x_start, y_start, t))
        t += reaction_delay

        # 2️⃣ Саккада + коррекции
        for i in range(self.points):
            alpha = i / self.points

            # нелинейное приближение (быстро → медленно)
            alpha = 1 - math.exp(-3 * alpha)

            # шум уменьшается ближе к цели
            noise_scale = (1 - alpha) * self.noise_level

            x = (
                    x_start + alpha * (x_target - x_start)
                    + random.uniform(-noise_scale, noise_scale)
            )
            y = (
                    y_start + alpha * (y_target - y_start)
                    + random.uniform(-noise_scale, noise_scale)
            )

            gaze_points.append((x, y, t))
            t += duration / self.points

        return gaze_points
