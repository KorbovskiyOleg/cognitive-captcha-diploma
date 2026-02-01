import statistics

def score_session(stimulus_scores, min_stimuli=3):
    """
    stimulus_scores: list[float] — список total score каждого стимула
    """

    if len(stimulus_scores) < min_stimuli:
        return 0.0, {
            "reason": "not_enough_data",
            "count": len(stimulus_scores)
        }

    mean_score = statistics.mean(stimulus_scores)
    stdev_score = statistics.pstdev(stimulus_scores)

    return mean_score, {
        "mean": mean_score,
        "stdev": stdev_score,
        "count": len(stimulus_scores)
    }
