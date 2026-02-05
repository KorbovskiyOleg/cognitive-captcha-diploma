from analysis.dynamics.velocity import compute_velocity_profile
from tracking.human_simulator import HumanLikeEyeTracker
from tracking.dummy_tracker import DummyEyeTracker
import config
import time


def run(tracker, label):
    print(f"\n=== {label} ===")

    stimulus_time = time.time()
    target_name = "top_right"
    target = config.CORNERS[target_name]

    gaze = tracker.collect(
        start_time=stimulus_time,
        duration=config.STIMULUS_DURATION,
        target=target
    )

    profile = compute_velocity_profile(gaze)

    print("Mean velocity:", round(profile.mean_velocity, 2))
    print("Max velocity :", round(profile.max_velocity, 2))
    print("Peak count   :", profile.peak_count)


if __name__ == "__main__":
    run(HumanLikeEyeTracker(), "HUMAN")
    run(DummyEyeTracker(), "DUMMY")
