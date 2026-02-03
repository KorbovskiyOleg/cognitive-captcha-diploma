import time
import matplotlib.pyplot as plt

import config
from tracking.human_simulator import HumanLikeEyeTracker
from tracking.dummy_tracker import DummyEyeTracker


# -----------------------------
# Генератор робот-траектории
# -----------------------------
def generate_robot_trajectory(start_x, start_y, target_x, target_y, stimulus_time):
    return [
        (start_x, start_y, stimulus_time),
        (target_x, target_y, stimulus_time)
    ]


def plot_all():
    target_name = "top_right"
    target_x, target_y = config.CORNERS[target_name]

    start_x = config.SCREEN_WIDTH / 2
    start_y = config.SCREEN_HEIGHT / 2

    stimulus_time = time.time()

    # 👤 Human-like
    human_tracker = HumanLikeEyeTracker()
    human_points = human_tracker.collect(
        start_time=stimulus_time,
        duration=config.STIMULUS_DURATION,
        target=(target_x, target_y)
    )

    # 🤖 Robot
    robot_points = generate_robot_trajectory(
        start_x, start_y, target_x, target_y, stimulus_time
    )

    # 🌪 Noise
    noise_tracker = DummyEyeTracker()
    noise_points = noise_tracker.collect(
        start_time=stimulus_time,
        duration=config.STIMULUS_DURATION
    )

    def unpack(points):
        return [x for x, y, t in points], [y for x, y, t in points]

    hx, hy = unpack(human_points)
    rx, ry = unpack(robot_points)
    nx, ny = unpack(noise_points)

    plt.figure()
    plt.plot(hx, hy, marker='o', label="Human-like")
    plt.plot(rx, ry, marker='x', linestyle='--', label="Robot")
    plt.plot(nx, ny, marker='.', linestyle=':', label="Noise")

    plt.scatter([target_x], [target_y], s=120, label="Target")

    plt.title("Gaze trajectory comparison")
    plt.xlabel("X (pixels)")
    plt.ylabel("Y (pixels)")
    plt.legend()
    plt.gca().invert_yaxis()
    plt.show()


if __name__ == "__main__":
    plot_all()
