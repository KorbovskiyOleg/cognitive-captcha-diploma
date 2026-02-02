import time
import matplotlib.pyplot as plt

import config
from tracking.human_simulator import HumanLikeEyeTracker


def plot_human_trajectory():
    tracker = HumanLikeEyeTracker()

    # выбираем стимул
    target_name = "top_right"
    target_x, target_y = config.CORNERS[target_name]

    stimulus_time = time.time()

    gaze_points = tracker.collect(
        start_time=stimulus_time,
        duration=config.STIMULUS_DURATION,
        target=(target_x, target_y)
    )

    xs = [x for x, y, t in gaze_points]
    ys = [y for x, y, t in gaze_points]

    plt.figure()
    plt.plot(xs, ys, marker='o')
    plt.scatter([target_x], [target_y], s=100)  # цель
    plt.title(f"Human-like gaze trajectory → {target_name}")
    plt.xlabel("X (pixels)")
    plt.ylabel("Y (pixels)")

    # экранная система координат
    plt.gca().invert_yaxis()

    plt.show()


if __name__ == "__main__":
    plot_human_trajectory()
