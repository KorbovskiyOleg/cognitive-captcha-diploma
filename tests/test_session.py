from analysis.session_scorer import score_session

def test_human_session():
    scores = [0.68, 0.71, 0.66, 0.70]
    total, details = score_session(scores)

    print("=== HUMAN SESSION ===")
    print("Total:", round(total, 3))
    print(details)
    print()

def test_robot_session():
    scores = [0.44, 0.45, 0.43, 0.44]
    total, details = score_session(scores)

    print("=== ROBOT SESSION ===")
    print("Total:", round(total, 3))
    print(details)
    print()

def test_noise_session():
    scores = [0.18, 0.22, 0.20, 0.19]
    total, details = score_session(scores)

    print("=== NOISE SESSION ===")
    print("Total:", round(total, 3))
    print(details)
    print()

if __name__ == "__main__":
    test_human_session()
    test_robot_session()
    test_noise_session()
