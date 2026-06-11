# точка входа
# создается сессия капчи
# инициализируются модули
# запускается цикл верификации
# принимается финальное решение - человек/бот
#
#
#

from app.session import CognitiveCaptchaSession
from tracking.real_eye_tracker import RealEyeTracker
from ui.ctk_stimulus_renderer import CtkStimulusRenderer


def main():
    renderer = CtkStimulusRenderer()
    renderer.init_window()

    eye_tracker = RealEyeTracker(
        gui_update_callback=renderer.root.update
    )

    def on_calibration_complete(calibration_data: dict):
        """Калибровка завершена, показываем приветственный экран."""
        print(f"[Main] Калибровка завершена")
        eye_tracker.set_calibration(calibration_data)

        def on_start(user_name: str):
            print(f"\n[Main] Пользователь: {user_name}")
            print("[Main] Запускаем сессию...")

            session = CognitiveCaptchaSession(
                eye_tracker=eye_tracker,
                stimulus_renderer=renderer
            )

            result = session.run_session()
            print("\n=== CAPTCHA RESULT ===")
            print(result)

            success = result.get("verdict", False)
            renderer.show_result(success)

            eye_tracker.stop()

        renderer.show_welcome_screen(on_start)

    def gaze_collector():
        """Функция для сбора gaze данных во время калибровки."""
        return eye_tracker.get_recent_gaze_samples(duration=2.0)

    print("[Main] Запускаю камеру и калибровку...")
    eye_tracker.start()

    # Сначала калибровка
    renderer.show_calibration_screen(gaze_collector, on_calibration_complete)
    renderer.root.mainloop()


if __name__ == "__main__":
    main()
