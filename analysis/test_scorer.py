import time
import random

from analysis.scorer import score_stimulus
import config

# функция генерации человеческой траектории
def generate_human_like_trajectory(
        start_x, start_y,
        target_x, target_y,
        stimulus_time,
        reaction_delay=0.35,   # 👈 ЧЕЛОВЕЧЕСКАЯ ЗАДЕРЖКА
        duration=1.5,
        points=20
):
    gaze_points = []

    # 1️⃣ Взгляд стоит на месте во время реакции
    t = stimulus_time
    gaze_points.append((start_x, start_y, t))

    t += reaction_delay

    # 2️⃣ Начинается движение
    for i in range(points):
        alpha = i / points

        x = start_x + alpha * (target_x - start_x) + random.uniform(-20, 20)
        y = start_y + alpha * (target_y - start_y) + random.uniform(-20, 20)

        gaze_points.append((x, y, t))
        t += duration / points

    return gaze_points

#==============================================================================================
#                               Тест №1 - Нормальный человек
#=============================================================================================
def test_human():
    stimulus_time = time.time()

    target_x, target_y = config.CORNERS["top_right"]
    start_x, start_y = config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2

    gaze = generate_human_like_trajectory(
        start_x, start_y,
        target_x, target_y,
        stimulus_time
    )

    total, details = score_stimulus(
        gaze, target_x, target_y, stimulus_time
    )

    print("=== HUMAN TEST ===")
    print("Total score:", round(total, 3))
    print("Details:", details)
    print()


if __name__ == "__main__":
    test_human()
    #test_bad_behavior()
    #test_perfect_bot()
