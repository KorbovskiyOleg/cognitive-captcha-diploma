import random
import config


class DummyEyeTracker:
    """
    Заглушка eye-tracker для тестирования сессии
    """

    def collect(self, start_time, duration):
        points = []
        t = start_time
        x = config.SCREEN_WIDTH / 2
        y = config.SCREEN_HEIGHT / 2

        for _ in range(20):
            x += random.uniform(-50, 50)
            y += random.uniform(-50, 50)
            points.append((x, y, t))
            t += duration / 20

        return points
