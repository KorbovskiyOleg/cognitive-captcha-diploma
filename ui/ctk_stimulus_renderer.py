"""
Рендерер стимулов на CustomTkinter с калибровкой eye-tracker.
"""

import customtkinter as ctk
from PIL import Image, ImageDraw
import time
import config
from typing import Callable, List, Tuple
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np
import io


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

    def show_result(self, success: bool, result: dict = None):
        """
        Показать экран результата с детальной информацией по признакам.

        Args:
            success: True если капча пройдена
            result: словарь с результатами сессии
        """
        if not self._initialized:
            self.init_window()

        self._hide_welcome()

        if self.image_label:
            self.image_label.destroy()

        # Затемнение фона
        overlay = ctk.CTkFrame(
            self.root,
            fg_color=("#f0f0f0", "#1a1a1a"),
            width=config.SCREEN_WIDTH,
            height=config.SCREEN_HEIGHT
        )
        overlay.place(x=0, y=0)

        # === ВЕРХНЯЯ ЧАСТЬ: Заголовок и итог ===
        title_card_width = 600
        title_card_height = 200
        title_card = ctk.CTkFrame(
            overlay,
            width=title_card_width,
            height=title_card_height,
            corner_radius=20,
            fg_color=("#2b2b2b", "#2b2b2b")
        )
        title_card.place(
            x=(config.SCREEN_WIDTH - title_card_width) // 2,
            y=30
        )
        title_card.pack_propagate(False)

        title = "✓ КАПЧА ПРОЙДЕНА" if success else "✗ КАПЧА НЕ ПРОЙДЕНА"
        color = ("#4CAF50", "#4CAF50") if success else ("#F44336", "#F44336")

        ctk.CTkLabel(
            title_card, text=title,
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=color
        ).pack(pady=(30, 5))

        if self.user_name:
            ctk.CTkLabel(
                title_card,
                text=f"Пользователь: {self.user_name}",
                font=ctk.CTkFont(size=16),
                text_color=("gray", "gray")
            ).pack(pady=(0, 10))

        # Итоговый скор
        final_score = result.get("final_score", 0.0) if result else 0.0
        ctk.CTkLabel(
            title_card,
            text=f"Итоговый скор: {final_score:.3f}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=("white", "white")
        ).pack()

        # === СРЕДНЯЯ ЧАСТЬ: Детальная информация ===
        details_width = 1600
        details_height = 650

        scrollable_frame = ctk.CTkScrollableFrame(
            overlay,
            width=details_width,
            height=details_height,
            corner_radius=15,
            fg_color=("#ffffff", "#2b2b2b")
        )
        scrollable_frame.place(
            x=(config.SCREEN_WIDTH - details_width) // 2,
            y=250
        )

        if result:
            self._render_result_details(scrollable_frame, result)
        else:
            ctk.CTkLabel(
                scrollable_frame,
                text="Нет детальной информации",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            ).pack(pady=20)

        # === НИЖНЯЯ ЧАСТЬ: Кнопка закрытия ===
        close_btn = ctk.CTkButton(
            overlay,
            text="Закрыть",
            font=ctk.CTkFont(size=18, weight="bold"),
            width=200,
            height=50,
            corner_radius=10,
            command=self.root.destroy
        )
        close_btn.place(
            x=(config.SCREEN_WIDTH - 200) // 2,
            y=config.SCREEN_HEIGHT - 80
        )

        self.root.update()

    def _render_result_details(self, parent, result: dict):
        """Рендерит детальную информацию о результатах."""

        # === Статистика сессии ===
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            stats_frame,
            text="📊 Статистика сессии",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("#2196F3", "#2196F3")
        ).pack(anchor="w")

        stats = result.get("stats", {})
        sequence = result.get("sequence", [])

        stats_text = (
            f"Средний скор: {stats.get('mean', 0):.3f}    |    "
            f"Стандартное отклонение: {stats.get('stdev', 0):.3f}    |    "
            f"Количество стимулов: {stats.get('count', 0)}    |    "
            f"Порог: {config.SESSION_THRESHOLD:.2f}"
        )
        ctk.CTkLabel(
            stats_frame,
            text=stats_text,
            font=ctk.CTkFont(size=14),
            text_color=("gray", "gray")
        ).pack(anchor="w", pady=(5, 0))

        seq_text = f"Порядок стимулов: {' → '.join(sequence)}"
        ctk.CTkLabel(
            stats_frame,
            text=seq_text,
            font=ctk.CTkFont(size=14),
            text_color=("gray", "gray")
        ).pack(anchor="w", pady=(5, 0))

        # Разделитель
        ctk.CTkFrame(parent, height=2, fg_color=("gray", "gray")).pack(
            fill="x", padx=20, pady=15
        )

        # === Детали по стимулам (сетка 2x2) ===
        ctk.CTkLabel(
            parent,
            text="📋 Детали по каждому стимулу",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("#2196F3", "#2196F3")
        ).pack(anchor="w", padx=20)

        stimuli_scores = result.get("stimuli", [])
        details = result.get("details", [])

        # Сетка 2 колонки
        grid_frame = ctk.CTkFrame(parent, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=20, pady=10)
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        for i, (score, detail) in enumerate(zip(stimuli_scores, details)):
            row = i // 2
            col = i % 2
            target_name = sequence[i] if i < len(sequence) else f"stimulus_{i}"

            self._render_stimulus_card(
                grid_frame, row, col,
                i + 1, target_name, score, detail
            )

    def _create_trajectory_plot(self, gaze_points, target_x, target_y, score):
        """
        Создаёт график траектории взгляда для одного стимула.
        Возвращает PIL Image.
        """
        if not gaze_points:
            return None

        # Извлекаем координаты
        x_coords = [p[0] for p in gaze_points]
        y_coords = [p[1] for p in gaze_points]
        times = [p[2] for p in gaze_points]

        # Нормализуем время для цветовой карты
        if len(times) > 1:
            time_norm = [(t - times[0]) / (times[-1] - times[0]) for t in times]
        else:
            time_norm = [0] * len(times)

        # Создаём фигуру
        fig, ax = plt.subplots(1, 1, figsize=(6, 4), dpi=100)
        fig.patch.set_facecolor('#2b2b2b')
        ax.set_facecolor('#1a1a1a')

        # Рисуем траекторию с цветовой картой по времени
        scatter = ax.scatter(
            x_coords, y_coords,
            c=time_norm,
            cmap='viridis',
            s=20,
            alpha=0.7,
            edgecolors='white',
            linewidth=0.5
        )

        # Рисуем линию траектории
        ax.plot(x_coords, y_coords, 'w-', linewidth=1, alpha=0.3)

        # Рисуем целевую точку
        ax.scatter(
            [target_x], [target_y],
            c='red',
            s=200,
            marker='X',
            edgecolors='white',
            linewidth=2,
            label='Цель',
            zorder=5
        )

        # Рисуем рамку целевой зоны
        half_w = config.BOUND_BOX_WIDTH / 2
        target_rect = plt.Rectangle(
            (target_x - half_w, target_y - half_w),
            config.BOUND_BOX_WIDTH,
            config.BOUND_BOX_WIDTH,
            fill=False,
            color='yellow',
            linewidth=2,
            linestyle='--',
            label='Целевая зона',
            zorder=3
        )
        ax.add_patch(target_rect)

        # Настройки осей
        ax.set_xlim(0, config.SCREEN_WIDTH)
        ax.set_ylim(0, config.SCREEN_HEIGHT)
        ax.set_aspect('equal')
        ax.invert_yaxis()  # Инвертируем Y чтобы было как на экране

        # Подписи
        ax.set_xlabel('X (пиксели)', color='white', fontsize=10)
        ax.set_ylabel('Y (пиксели)', color='white', fontsize=10)
        ax.set_title(
            f'Траектория взгляда\nScore: {score:.3f}',
            color='white',
            fontsize=12,
            fontweight='bold'
        )

        # Цвет сетки
        ax.grid(True, alpha=0.2, color='gray')
        ax.tick_params(colors='white')

        # Легенда
        ax.legend(loc='upper right', facecolor='#2b2b2b', edgecolor='white',
                  labelcolor='white', fontsize=8)

        # Добавляем colorbar для времени
        cbar = plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Время (нормализованное)', color='white', fontsize=8)
        cbar.ax.tick_params(labelsize=7, colors='white')

        plt.tight_layout()

        # Конвертируем в PIL Image
        canvas = FigureCanvasAgg(fig)
        buf = io.BytesIO()
        canvas.print_figure(buf, format='png', bbox_inches='tight',
                            facecolor=fig.get_facecolor())
        buf.seek(0)

        img = Image.open(buf)
        plt.close(fig)

        return img

    def _render_stimulus_card(self, parent, row, col, num, target_name, score, detail):
        """Рендерит карточку одного стимула с графиком траектории."""

        # Цвет карточки в зависимости от score
        if score >= 0.7:
            border_color = ("#4CAF50", "#4CAF50")  # зелёный
        elif score >= 0.5:
            border_color = ("#FF9800", "#FF9800")  # оранжевый
        else:
            border_color = ("#F44336", "#F44336")  # красный

        card = ctk.CTkFrame(
            parent,
            corner_radius=10,
            fg_color=("#f9f9f9", "#363636"),
            border_width=2,
            border_color=border_color
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        # Заголовок карточки
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(
            header_frame,
            text=f"Стимул #{num}: {target_name}",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        # Скор справа
        score_color = ("#4CAF50", "#4CAF50") if score >= 0.7 else (
            ("#FF9800", "#FF9800") if score >= 0.5 else ("#F44336", "#F44336")
        )
        ctk.CTkLabel(
            header_frame,
            text=f"{score:.3f}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=score_color
        ).pack(side="right")

        # Разделитель
        ctk.CTkFrame(card, height=1, fg_color=("gray", "gray")).pack(
            fill="x", padx=15, pady=5
        )

        # === НОВОЕ: График траектории ===
        if "gaze_points" in detail and "target_x" in detail:
            gaze_points = detail["gaze_points"]
            target_x = detail["target_x"]
            target_y = detail["target_y"]

            try:
                trajectory_img = self._create_trajectory_plot(
                    gaze_points, target_x, target_y, score
                )

                if trajectory_img:
                    # Конвертируем в CTkImage
                    ctk_img = ctk.CTkImage(
                        light_image=trajectory_img,
                        dark_image=trajectory_img,
                        size=(350, 230)  # Размер графика
                    )

                    img_label = ctk.CTkLabel(
                        card,
                        image=ctk_img,
                        text=""
                    )
                    img_label.pack(pady=10)
            except Exception as e:
                print(f"[WARNING] Не удалось создать график траектории: {e}")
        # ===========================================

        # Содержимое
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.pack(fill="x", padx=15, pady=(5, 10))

        if "error" in detail:
            # Ошибка
            ctk.CTkLabel(
                content_frame,
                text=f"❌ Ошибка: {detail['error']}",
                font=ctk.CTkFont(size=13),
                text_color=("#F44336", "#F44336")
            ).pack(anchor="w")
        elif "velocity_validation" in detail:
            # Velocity validation failed
            ctk.CTkLabel(
                content_frame,
                text=f"❌ Velocity: {detail['velocity_validation']}",
                font=ctk.CTkFont(size=13),
                text_color=("#F44336", "#F44336")
            ).pack(anchor="w")

            vel_details = detail.get("velocity_details", {})
            if vel_details:
                ctk.CTkLabel(
                    content_frame,
                    text=f"   Детали: {vel_details}",
                    font=ctk.CTkFont(size=11),
                    text_color=("gray", "gray")
                ).pack(anchor="w")
        else:
            # Нормальные признаки
            feature_names = {
                "latency": "⏱ Latency (задержка)",
                "distance_error": "📏 Distance (расстояние)",
                "angle_error": "🧭 Angle (угол)",
                "out_of_bounds_ratio": "🎯 In-bounds (в зоне)",
                "dispersion": "〰️ Dispersion (разброс)"
            }

            for key, display_name in feature_names.items():
                if key in detail:
                    value = detail[key]
                    # Форматирование значения
                    if isinstance(value, (int, float)):
                        value_str = f"{value:.3f}"
                        # Цвет в зависимости от значения
                        if value >= 0.7:
                            val_color = ("#4CAF50", "#4CAF50")
                        elif value >= 0.4:
                            val_color = ("#FF9800", "#FF9800")
                        else:
                            val_color = ("#F44336", "#F44336")
                    else:
                        value_str = str(value)
                        val_color = ("black", "white")

                    row_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
                    row_frame.pack(fill="x", pady=2)

                    ctk.CTkLabel(
                        row_frame,
                        text=display_name,
                        font=ctk.CTkFont(size=12),
                        anchor="w"
                    ).pack(side="left")

                    ctk.CTkLabel(
                        row_frame,
                        text=value_str,
                        font=ctk.CTkFont(size=12, weight="bold"),
                        text_color=val_color
                    ).pack(side="right")

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