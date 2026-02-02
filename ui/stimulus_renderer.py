# визуальные стимулы

# показать картинку в нужном углу
# убрать картинку
# управлять временем отображения

# просто показывает стимулы
# использует assets/images

import time


class StimulusRenderer:
    """
    Временный renderer (без UI)
    """

    def show(self, target_name):
        print(f"[STIMULUS] Look at: {target_name}")
        time.sleep(0.1)
