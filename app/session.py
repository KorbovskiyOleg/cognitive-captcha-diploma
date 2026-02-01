# логика одной капчи

# список стимулов
# текущее состояние
# накопление результатов
# подсчет total_score

# знает что должно произойти


from analysis.session_scorer import score_session
import config


def evaluate_session(stimulus_scores):
    """
    Главная функция принятия решения.
    Возвращает (verdict, details)
    """

    mean_score, stats = score_session(
        stimulus_scores,
        min_stimuli=config.MIN_STIMULI
    )

    if "reason" in stats:
        return "invalid", stats

    stdev = stats["stdev"]

    # 🚫 слишком низкий средний score
    if mean_score < config.SESSION_ROBOT_THRESHOLD:
        return "bot", {
            **stats,
            "reason": "low_mean_score"
        }

    # ⚠️ подозрительно стабильное поведение
    if stdev < config.MIN_STDEV:
        return "bot", {
            **stats,
            "reason": "too_stable"
        }

    # ⚠️ слишком хаотично
    if stdev > config.MAX_STDEV:
        return "uncertain", {
            **stats,
            "reason": "too_chaotic"
        }

    # ✅ нормальный человек
    if mean_score >= config.SESSION_HUMAN_THRESHOLD:
        return "human", stats

    # 🤔 пограничный случай
    return "uncertain", {
        **stats,
        "reason": "borderline"
    }
