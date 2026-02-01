from app.session import evaluate_session


def test_human():
    scores = [0.68, 0.71, 0.66, 0.70]
    verdict, details = evaluate_session(scores)
    print("HUMAN:", verdict, details)


def test_robot():
    scores = [0.44, 0.45, 0.43, 0.44]
    verdict, details = evaluate_session(scores)
    print("ROBOT:", verdict, details)


def test_noise():
    scores = [0.18, 0.22, 0.20, 0.19]
    verdict, details = evaluate_session(scores)
    print("NOISE:", verdict, details)


if __name__ == "__main__":
    test_human()
    test_robot()
    test_noise()
