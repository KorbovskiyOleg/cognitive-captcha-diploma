"""
Рендерер стимулов на CustomTkinter с калибровкой eye-tracker.
"""

import customtkinter as ctk
from PIL import Image, ImageDraw
import time
import config
from typing import Callable, List, Tuple


class CtkStimulusRenderer:
    """
    Показывает стимулы в окне CustomTkinter.
    """

    def __init__(self):
        self.root: ctk.CTk = None
        self.image_label: ctk.CTkLabel = None
        self._initialized = False
        self.user_name: str = ""
        self._welcome_card = None
        self._calibration_target = None

    def init_window(self):
        """Создание полноэкранного окна."""
        if self._initialized:
            return

        self.root = ctk.CTk()
        self.root.title("Когнитивная CAPTCHA")
        self.root.geometry(f"{config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT}+0+0")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        ctk.set_appearance_mode("dark")
        self._initialized = True

    def show_calibration_screen(self, gaze_collector: Callable[[], List[Tuple[float, float]]],
                                on_complete: Callable[[dict], None]):
        """
        Калибровочный экран: пользователь смотрит в 5 точек.

        Args:
            gaze_collector: функция, возвращающая список (gaze_x, gaze_y) за последние 2 секунды
            on_complete: коллбэк с калибровочными данными
        """
        if not self._initialized:
            self.init_window()

        # Очистка окна
        for widget in self.root.winfo_children():
            widget.destroy()

        self._hide_welcome()

        # Инструкция
        instruction = ctk.CTkLabel(
            self.root,
            text="КАЛИБРОВКА\n\nСмотрите на красные точки\nНе двигайте головой",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="white",
            justify="center"
        )
        instruction.place(
            x=(config.SCREEN_WIDTH - 500) // 2,
            y=100
        )

        # Прогресс
        progress_label = ctk.CTkLabel(
            self.root,
            text="Точка 1 из 5",
            font=ctk.CTkFont(size=18),
            text_color="gray"
        )
        progress_label.place(
            x=(config.SCREEN_WIDTH - 200) // 2,
            y=200
        )

        # 5 точек калибровки (углы + центр)
        calibration_points = [
            (100, 100),      # top_left
            (1820, 100),     # top_right
            (960, 540),      # center
            (100, 980),      # bottom_left
            (1820, 980),     # bottom_right
        ]

        calibration_data = []  # (screen_x, screen_y, avg_gaze_x, avg_gaze_y)

        def show_next_point(idx):
            if idx >= len(calibration_points):
                # Калибровка завершена
                instruction.destroy()
                progress_label.destroy()
                if self._calibration_target:
                    self._calibration_target.destroy()

                # Вычисляем коэффициенты маппинга
                calibration_result = self._compute_calibration(calibration_data)
                on_complete(calibration_result)
                return

            target_x, target_y = calibration_points[idx]
            progress_label.configure(text=f"Точка {idx + 1} из {len(calibration_points)}")

            # Показываем точку
            if self._calibration_target:
                self._calibration_target.destroy()

            # Большая красная точка
            self._calibration_target = ctk.CTkLabel(
                self.root,
                text="●",
                font=ctk.CTkFont(size=80),
                text_color="red"
            )
            self._calibration_target.place(x=target_x - 40, y=target_y - 40)

            # Таймер обратного отсчёта
            countdown_label = ctk.CTkLabel(
                self.root,
                text="3",
                font=ctk.CTkFont(size=48, weight="bold"),
                text_color="yellow"
            )
            countdown_label.place(
                x=(config.SCREEN_WIDTH - 50) // 2,
                y=300
            )

            # Собираем gaze данные 3 секунды
            countdown = [3]

            def update_countdown():
                countdown[0] -= 1
                if countdown[0] > 0:
                    countdown_label.configure(text=str(countdown[0]))
                    self.root.after(1000, update_countdown)
                else:
                    # Время вышло, собираем данные
                    countdown_label.destroy()
                    gaze_samples = gaze_collector()

                    if gaze_samples:
                        avg_gaze_x = sum(g[0] for g in gaze_samples) / len(gaze_samples)
                        avg_gaze_y = sum(g[1] for g in gaze_samples) / len(gaze_samples)
                        calibration_data.append((target_x, target_y, avg_gaze_x, avg_gaze_y))
                        print(f"[Calibration] Точка {idx + 1}: screen=({target_x}, {target_y}), "
                              f"gaze=({avg_gaze_x:.3f}, {avg_gaze_y:.3f}), samples={len(gaze_samples)}")

                    # Следующая точка через 0.5 секунды
                    self.root.after(500, lambda: show_next_point(idx + 1))

            self.root.after(1000, update_countdown)

        show_next_point(0)
        self.root.update()

    def _compute_calibration(self, calibration_data: List[Tuple[float, float, float, float]]) -> dict:
        """
        Вычисляет коэффициенты маппинга: gaze → screen.

        Линейная регрессия:
        screen_x = scale_x * gaze_x + offset_x
        screen_y = scale_y * gaze_y + offset_y
        """
        if len(calibration_data) < 2:
            print("[Calibration] Недостаточно данных, используем значения по умолчанию")
            return {
                "scale_x": config.SCREEN_WIDTH,
                "scale_y": config.SCREEN_HEIGHT,
                "offset_x": 0.0,
                "offset_y": 0.0
            }

        # Извлекаем данные
        screen_x = [d[0] for d in calibration_data]
        screen_y = [d[1] for d in calibration_data]
        gaze_x = [d[2] for d in calibration_data]
        gaze_y = [d[3] for d in calibration_data]

        # Линейная регрессия для X
        n = len(gaze_x)
        sum_gx = sum(gaze_x)
        sum_sx = sum(screen_x)
        sum_gx_sx = sum(g * s for g, s in zip(gaze_x, screen_x))
        sum_gx2 = sum(g * g for g in gaze_x)

        denominator_x = n * sum_gx2 - sum_gx * sum_gx
        if abs(denominator_x) < 1e-10:
            scale_x = 1.0
            offset_x = 0.0
        else:
            scale_x = (n * sum_gx_sx - sum_gx * sum_sx) / denominator_x
            offset_x = (sum_sx - scale_x * sum_gx) / n

        # Линейная регрессия для Y
        sum_gy = sum(gaze_y)
        sum_sy = sum(screen_y)
        sum_gy_sy = sum(g * s for g, s in zip(gaze_y, screen_y))
        sum_gy2 = sum(g * g for g in gaze_y)

        denominator_y = n * sum_gy2 - sum_gy * sum_gy
        if abs(denominator_y) < 1e-10:
            scale_y = 1.0
            offset_y = 0.0
        else:
            scale_y = (n * sum_gy_sy - sum_gy * sum_sy) / denominator_y
            offset_y = (sum_sy - scale_y * sum_gy) / n

        calibration_result = {
            "scale_x": scale_x,
            "scale_y": scale_y,
            "offset_x": offset_x,
            "offset_y": offset_y
        }

        print(f"\n[Calibration] Результаты:")
        print(f"  scale_x = {scale_x:.2f}, offset_x = {offset_x:.2f}")
        print(f"  scale_y = {scale_y:.2f}, offset_y = {offset_y:.2f}")
        print(f"  Формула: screen_x = {scale_x:.2f} * gaze_x + {offset_x:.2f}")
        print(f"  Формула: screen_y = {scale_y:.2f} * gaze_y + {offset_y:.2f}\n")

        return calibration_result

    def show_welcome_screen(self, on_start: Callable[[str], None]):
        """
        Приветственный экран с полем ввода имени и кнопкой Старт.
        """
        if not self._initialized:
            self.init_window()

        # Очистка окна
        for widget in self.root.winfo_children():
            widget.destroy()

        # Центральная карточка
        card_width = 500
        card_height = 400
        self._welcome_card = ctk.CTkFrame(
            self.root,
            width=card_width,
            height=card_height,
            corner_radius=20,
            fg_color=("#2b2b2b", "#1a1a1a")
        )
        self._welcome_card.place(
            x=(config.SCREEN_WIDTH - card_width) // 2,
            y=(config.SCREEN_HEIGHT - card_height) // 2
        )
        self._welcome_card.pack_propagate(False)

        # Заголовок
        ctk.CTkLabel(
            self._welcome_card,
            text="Когнитивная CAPTCHA",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=("#ffffff", "#ffffff")
        ).pack(pady=(60, 10))

        # Подпись
        ctk.CTkLabel(
            self._welcome_card,
            text="Введите ваше имя и нажмите «Старт»",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(pady=(0, 30))

        # Поле ввода имени
        name_entry = ctk.CTkEntry(
            self._welcome_card,
            placeholder_text="Ваше имя",
            font=ctk.CTkFont(size=18),
            width=300,
            height=45,
            corner_radius=10
        )
        name_entry.pack(pady=(0, 25))
        name_entry.focus_set()

        # Кнопка Старт
        def handle_start():
            name = name_entry.get().strip()
            if not name:
                name = "Аноним"
            self.user_name = name
            on_start(name)

        start_btn = ctk.CTkButton(
            self._welcome_card,
            text="Старт",
            font=ctk.CTkFont(size=20, weight="bold"),
            width=200,
            height=50,
            corner_radius=10,
            command=handle_start
        )
        start_btn.pack(pady=(0, 40))

        # Enter тоже запускает
        name_entry.bind("<Return>", lambda e: handle_start())

        # Обновляем окно
        self.root.update()

    def _hide_welcome(self):
        """Скрыть приветственную карточку."""
        if self._welcome_card:
            self._welcome_card.destroy()
            self._welcome_card = None

    def show(self, target_name: str):
        """
        Показать стимул в позиции из config.CORNERS[target_name].
        """
        if not self._initialized:
            self.init_window()

        self._hide_welcome()

        if self.image_label:
            self.image_label.destroy()

        target_x, target_y = config.CORNERS[target_name]

        half_size = config.STIMULUS_SIZE // 2
        x_pos = target_x - half_size
        y_pos = target_y - half_size

        image = self._make_stimulus(target_name)

        self.image_label = ctk.CTkLabel(
            self.root,
            image=image,
            text="",
            fg_color="transparent"
        )
        self.image_label.place(x=x_pos, y=y_pos)

        self.root.update()
        time.sleep(0.1)

    def show_result(self, success: bool):
        """Показать экран результата по центру."""
        if not self._initialized:
            self.init_window()

        self._hide_welcome()

        if self.image_label:
            self.image_label.destroy()

        # Затемнение фона
        overlay = ctk.CTkFrame(
            self.root,
            fg_color=("white", "black"),
            width=config.SCREEN_WIDTH,
            height=config.SCREEN_HEIGHT
        )
        overlay.place(x=0, y=0)

        # Карточка результата
        card_width = 500
        card_height = 300
        card = ctk.CTkFrame(
            overlay,
            width=card_width,
            height=card_height,
            corner_radius=20,
            fg_color=("#2b2b2b", "#1a1a1a")
        )
        card.place(
            x=(config.SCREEN_WIDTH - card_width) // 2,
            y=(config.SCREEN_HEIGHT - card_height) // 2
        )
        card.pack_propagate(False)

        title = "✓ Капча пройдена" if success else "✗ Капча не пройдена"
        color = "green" if success else "red"

        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=color
        ).pack(pady=(50, 10))

        if self.user_name:
            ctk.CTkLabel(
                card,
                text=f"Пользователь: {self.user_name}",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            ).pack(pady=(0, 20))

        ctk.CTkButton(
            card, text="Закрыть",
            command=self.root.destroy,
            width=160, height=40
        ).pack()

        self.root.update()

    def close(self):
        """Закрытие окна."""
        if self.root:
            self.root.destroy()

    def _make_stimulus(self, label: str) -> ctk.CTkImage:
        """Создаёт картинку 200x200 с Target по центру."""
        size = config.STIMULUS_SIZE

        img = Image.new("RGB", (size, size), (100, 120, 140))
        draw = ImageDraw.Draw(img)

        if label:
            bbox = draw.textbbox((0, 0), label)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                ((size - tw) / 2, 10),
                label,
                fill=(255, 255, 255)
            )

        cx, cy = size // 2, size // 2
        radius = 20
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            outline="red", width=3
        )
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill="red")

        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))