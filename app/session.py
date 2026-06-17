# логика одной капчи

# список стимулов
# текущее состояние
# накопление результатов
# подсчет total_score

# знает что должно произойти

import time
import random  # ← НОВЫЙ ИМПОРТ

from analysis.scorer import score_stimulus
from analysis.session_scorer import score_session
from analysis.dynamics.velocity import compute_velocity_profile
from analysis.dynamics.velocity_validator import validate_velocity
import config


class CognitiveCaptchaSession:
    """
    Управляет одной сессией когнитивной CAPTCHA
    """

    def __init__(self, eye_tracker, stimulus_renderer):
        self.eye_tracker = eye_tracker
        self.stimulus_renderer = stimulus_renderer

        self.stimulus_scores = []
        self.raw_scores = []

    def run_stimulus(self, target_name):
        """
        Запуск одного когнитивного стимула
        """
        target_x, target_y = config.CORNERS[target_name]

        stimulus_time = time.time()
        self.stimulus_renderer.show(target_name)

        gaze_points = self.eye_tracker.collect(
            start_time=stimulus_time,
            duration=config.STIMULUS_DURATION,
            target=(target_x, target_y)
        )

        if len(gaze_points) < 2:
            self.stimulus_scores.append(0.0)
            self.raw_scores.append({"error": "no_gaze_data"})
            return 0.0, {"error": "no_gaze_data"}

        profile = compute_velocity_profile(gaze_points)
        if profile is None:
            self.stimulus_scores.append(0.0)
            self.raw_scores.append({"error": "velocity_profile_failed"})
            return 0.0, {"error": "velocity_profile_failed"}

        validation = validate_velocity(profile)

        if not validation.is_valid:
            self.stimulus_scores.append(0.0)
            self.raw_scores.append({
                "velocity_validation": validation.reason,
                "velocity_details": validation.details
            })
            return 0.0, {"velocity_validation": validation.reason}

        total, details = score_stimulus(
            gaze_points,
            target_x,
            target_y,
            stimulus_time
        )

        self.stimulus_scores.append(total)
        #self.raw_scores.append(details)

        # === сохраняем точки и детали ===
        details_with_trajectory = {
            **details,
            "gaze_points": gaze_points,  # Сохраняем траекторию
            "target_x": target_x,
            "target_y": target_y
        }
        self.raw_scores.append(details_with_trajectory)
        # ============================================

        return total, details_with_trajectory



    def run_session(self):
        """
        Полный цикл CAPTCHA с рандомным порядком стимулов
        """
        # === РАНДОМИЗАЦИЯ ПОРЯДКА ===
        # Создаём копию последовательности чтобы не менять оригинал в config
        sequence = list(config.STIMULUS_SEQUENCE)

        # Перемешиваем
        random.shuffle(sequence)

        # Логируем получившийся порядок
        print(f"\n[CognitiveCaptchaSession] Порядок стимулов: {sequence}")
        print(f"[CognitiveCaptchaSession] Количество стимулов: {len(sequence)}\n")

        # Проходим по перемешанной последовательности
        for target in sequence:
            self.run_stimulus(target)
            time.sleep(config.INTER_STIMULUS_INTERVAL)

        final_score, stats = score_session(self.stimulus_scores)
        verdict = final_score >= config.SESSION_THRESHOLD

        return {
            "final_score": final_score,
            "verdict": verdict,
            "stimuli": self.stimulus_scores,
            "details": self.raw_scores,
            "stats": stats,
            "sequence": sequence  # ← ДОБАВЛЯЕМ в результат
        }
