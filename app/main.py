# точка входа
# создается сессия капчи
# инициализируются модули
# запускается цикл верификации
# принимается финальное решение - человек/бот
#
#
#

from app.session import CognitiveCaptchaSession
from tracking.dummy_tracker import DummyEyeTracker
from ui.stimulus_renderer import StimulusRenderer


def main():
    session = CognitiveCaptchaSession(
        eye_tracker=DummyEyeTracker(),
        stimulus_renderer=StimulusRenderer()
    )

    result = session.run_session()
    print("\n=== CAPTCHA RESULT ===")
    print(result)


if __name__ == "__main__":
    main()
