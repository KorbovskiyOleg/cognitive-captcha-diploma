# Сценарий защиты проекта: 8 смысловых частей

Этот документ описывает расширенный сценарий представления дипломного проекта на слайдах. Он не привязан строго к одному слайду на одну часть: каждая часть может занимать один или несколько слайдов.

> GitHub-ссылка для титульного/вводного слайда: `https://github.com/<your-login>/cognitive-captcha-diploma`  
> Замените `<your-login>` на реальный логин владельца репозитория перед финальной защитой.

## 1. Вводная часть

### Что обычно пишут во вводной части

Во вводной части презентации дипломного проекта обычно указывают:

- тему дипломной работы;
- ФИО автора;
- учебную группу, кафедру или направление подготовки;
- ФИО научного руководителя;
- актуальность темы;
- краткую постановку проблемы;
- цель работы;
- объект и предмет исследования;
- используемые технологии;
- ссылку на репозиторий проекта.

### Рекомендуемый текст для слайда

**Тема:** Система CAPTCHA на основе анализа траекторий взгляда с использованием eye-tracking.

**Актуальность:** классические CAPTCHA становятся менее устойчивыми к современным ботам и нейросетевым системам распознавания. Поэтому требуется исследовать новые поведенческие способы проверки пользователя.

**Цель:** разработать ядро CAPTCHA-системы, которое анализирует траекторию взгляда пользователя и принимает решение о правдоподобии человеческого поведения.

**GitHub:** `https://github.com/<your-login>/cognitive-captcha-diploma`

### Что сказать устно

> В работе рассматривается альтернативный подход к CAPTCHA. Вместо того чтобы просить пользователя вводить текст или выбирать объекты на картинке, система анализирует то, как пользователь переводит взгляд к визуальному стимулу. Такой подход относится к поведенческой проверке, потому что нас интересует не только результат действия, а динамика движения.

## 2. Идея проекта

### Описание идеи

Идея проекта состоит в том, чтобы использовать траекторию взгляда как поведенческий признак. Пользователю показываются визуальные стимулы, например в углах экрана. Система собирает последовательность gaze-точек `(x, y, t)`, анализирует задержку реакции, направление движения, расстояние до цели, выход за допустимую область и динамику скорости.

Идея такого подхода была предложена **Намиотом Д. Е.** В рамках проекта она реализована как программный прототип ядра Cognitive CAPTCHA.

### Какие проблемы решает идея

- снижает зависимость CAPTCHA от текстового или визуального распознавания;
- добавляет поведенческий фактор проверки;
- усложняет прохождение CAPTCHA простым скриптом;
- позволяет анализировать не только конечный ответ, но и процесс движения;
- создаёт основу для дальнейшего подключения реального eye-tracker.

### Промпт для генерации изображения

```text
A futuristic academic illustration of a Cognitive CAPTCHA concept proposed as an eye-tracking security system: a user looking at visualization targets on a computer screen, glowing gaze trajectory points, cybersecurity atmosphere, dark navy background, cyan and violet highlights, clean scientific presentation style, no text, 16:9.
```

## 3. Архитектура

### Описание архитектуры

Проект построен как модульный pipeline:

```text
app/main.py
    │
    ▼
app/session.py
    │
    ├── ui/stimulus_renderer.py
    ├── tracking/HumanLikeEyeTracker
    ├── analysis/dynamics/velocity.py
    ├── analysis/dynamics/velocity_validator.py
    ├── analysis/scorer.py
    └── analysis/session_scorer.py
```

Главный управляющий блок — `CognitiveCaptchaSession`. Он не занимается математикой и не зависит от конкретного UI. Он связывает между собой показ стимула, сбор gaze-данных, velocity validation, scoring и итоговое решение.

### Чем хороша архитектура

- **Разделение ответственности:** UI, tracking, scoring и session orchestration находятся в разных модулях.
- **Расширяемость:** можно заменить `HumanLikeEyeTracker` на реальный eye-tracker, не переписывая scoring.
- **Тестируемость:** математические функции можно тестировать отдельно от интерфейса.
- **Конфигурируемость:** ключевые параметры вынесены в `config.py`.
- **Понятный pipeline:** данные проходят последовательные стадии обработки.

### Как архитектура позволяет развивать проект

```text
текущий симулятор gaze-точек
        │ заменить
        ▼
OpenCV / MediaPipe / webcam eye-tracking
        │ расширить
        ▼
server-side validation + web UI
        │ улучшить
        ▼
ML-классификатор по реальным траекториям
```

### Альтернативные варианты архитектуры

1. **Монолитная архитектура**  
   Вся логика находится в одном файле. Подходит для быстрого прототипа, но плохо масштабируется.

2. **MVC/MVP архитектура**  
   UI отделяется от модели и контроллера. Хороший вариант для полноценного графического приложения.

3. **Client-server архитектура**  
   Клиент собирает gaze-данные, сервер принимает решение. Это лучше для production, потому что правила скоринга сложнее подменить на клиенте.

4. **Event-driven архитектура**  
   События `stimulus_shown`, `gaze_collected`, `score_computed` передаются через очередь. Подходит для сложных систем с асинхронной обработкой.

### Промпты для генерации изображений

```text
A clean architecture diagram for a Cognitive CAPTCHA eye-tracking project, showing modules app/session, UI stimulus renderer, tracking gaze collector, velocity analysis, scoring engine, session decision, and config. Dark navy background, cyan arrows, violet module blocks, modern academic software architecture style, no text or minimal readable labels, 16:9.
```

```text
A futuristic modular software architecture visualization: eye-tracking CAPTCHA pipeline from visualization stimulus to gaze collection, velocity validation, feature scoring, final human/bot verdict. Dark cyber security style, glowing data flow lines, clean blocks, 16:9 presentation graphic.
```

## 4. Конфиг

### Какие настройки используются

В `config.py` задаются основные параметры проекта:

- размеры экрана: `SCREEN_WIDTH`, `SCREEN_HEIGHT`;
- список целевых углов: `CORNERS`;
- длительность стимула: `STIMULUS_DURATION`;
- пауза между стимулами: `INTER_STIMULUS_INTERVAL`;
- размер допустимой зоны вокруг цели: `BOUND_BOX_WIDTH`, `BOUND_BOX_HEIGHT`;
- параметры latency: `MIN_LATENCY`, `OPT_LATENCY`, `MAX_LATENCY`;
- веса признаков: `FEATURE_WEIGHTS`;
- пороги решения: `SESSION_THRESHOLD`, `SESSION_HUMAN_THRESHOLD`, `SESSION_ROBOT_THRESHOLD`;
- последовательность стимулов: `STIMULUS_SEQUENCE`.

### Как можно расширить конфиг под конкретные задачи

- добавить разные профили сложности: easy / normal / strict;
- настраивать размер target-zone под разрешение экрана;
- задавать разные последовательности стимулов;
- добавлять случайную генерацию целей;
- хранить настройки UI: цвет, размер стимула, длительность анимации;
- хранить настройки eye-tracker: частота кадров, сглаживание, калибровка;
- добавлять server-side параметры безопасности.

### Связь конфига с UI

```text
config.py
   │
   ├── размеры экрана ─────────────► UI layout
   ├── координаты целей ───────────► позиции стимулов
   ├── длительность стимула ───────► таймер показа
   ├── bounding box ───────────────► подсветка допустимой зоны
   └── threshold/weights ──────────► панель настройки сложности
```

### Промпт для генерации UI параметров конфигурации

```text
A polished dark themed configuration dashboard UI for an eye-tracking Cognitive CAPTCHA system. Show controls for screen size, stimulus duration, target positions, latency thresholds, feature weights, session threshold, bounding box size, and difficulty profile. Cybersecurity academic style, cyan and violet accents, clean cards and sliders, no brand names, 16:9.
```

## 5. Немного математики расчёта траекторий

### Основные формулы проекта

**1. Точка взгляда**

```text
G_i = (x_i, y_i, t_i)
```

**2. Движение от старта к цели**

```text
P(alpha) = P_start + alpha * (P_target - P_start)
```

**3. Экспоненциальное easing-преобразование**

```text
alpha = 1 - e^(-4 * i/N)
```

**4. Затухающий шум**

```text
noise_scale = (1 - alpha) * noise_level
```

**5. Евклидово расстояние**

```text
distance = sqrt((x2 - x1)^2 + (y2 - y1)^2)
```

**6. Скорость между соседними точками**

```text
velocity = distance / Δt
```

**7. Угол движения к цели**

```text
cos(theta) = dot(v_actual, v_target) / (|v_actual| * |v_target|)
theta = arccos(cos(theta))
```

**8. Итоговый score**

```text
total_score = Σ(feature_score_i * weight_i)
```

### Промпты для генерации изображений

**Профиль скорости**

```text
A scientific velocity profile chart for eye-tracking gaze movement: time axis, velocity axis, several highlighted peaks, mean velocity line, saccade-like motion, dark navy background, cyan curve, yellow mean line, academic presentation style, 16:9.
```

**Latency**

```text
An educational diagram explaining reaction latency in eye-tracking CAPTCHA: stimulus appears, short cognitive delay, gaze starts moving, timeline with marked latency interval, dark background, cyan and violet accents, clean labels, 16:9.
```

**Distance error**

```text
A clean diagram of gaze points around a target on a computer screen, showing distances from each point to the target and average distance error, dark UI grid, glowing cyan points, yellow target, academic style, 16:9.
```

**Angle error**

```text
A vector geometry diagram for eye-tracking CAPTCHA showing actual gaze movement vector, target direction vector, and angle error theta between them. Dark navy background, cyan and violet arrows, clean mathematical labels, 16:9.
```

**Out-of-bounds ratio**

```text
A presentation diagram showing a bounding box around a visualization target and gaze points inside and outside it, explaining out-of-bounds ratio for eye-tracking CAPTCHA scoring, dark cyber style, cyan points, red outside points, 16:9.
```

## 6. Интеграция в другие системы

### Варианты встраивания

1. **Веб-приложение**  
   CAPTCHA подключается к форме входа, регистрации или подтверждения действия.

2. **Desktop-приложение**  
   Может использоваться в защищённых рабочих местах, экзаменационных системах или корпоративных приложениях.

3. **Серверная система проверки**  
   Клиент собирает gaze-точки, сервер выполняет scoring и принимает решение.

4. **Микросервис безопасности**  
   Cognitive CAPTCHA работает как отдельный сервис, к которому обращаются другие приложения.

5. **Система онлайн-экзаменов**  
   Eye-tracking может использоваться не только как CAPTCHA, но и как часть proctoring-механизма.

### ASCII-схема 1: интеграция в web-login

```text
┌──────────────┐       ┌──────────────────────┐       ┌──────────────┐
│ Browser UI   │──────►│ Cognitive CAPTCHA JS │──────►│ Backend API  │
│ login form   │       │ gaze collection      │       │ verification │
└──────┬───────┘       └──────────┬───────────┘       └──────┬───────┘
       │                          │                          │
       ▼                          ▼                          ▼
 user credentials          gaze_points                 allow / deny
```

### ASCII-схема 2: server-side validation

```text
┌──────────────┐
│ Client app   │
│ collect gaze │
└──────┬───────┘
       │ encrypted gaze session
       ▼
┌────────────────────────┐
│ CAPTCHA Verification   │
│ velocity + scoring     │
└──────┬─────────────────┘
       │ verdict + risk score
       ▼
┌──────────────┐
│ Main system  │
│ auth/action  │
└──────────────┘
```

### ASCII-схема 3: микросервис

```text
┌─────────────┐   request   ┌──────────────────────┐
│ Web portal  │────────────►│ Cognitive CAPTCHA API│
└─────────────┘             └──────────┬───────────┘
┌─────────────┐   request              │
│ Exam system │────────────►           │ shared scoring core
└─────────────┘                        │
┌─────────────┐   request              ▼
│ Mobile app  │────────────►  ┌────────────────────┐
└─────────────┘               │ verdict + telemetry│
                              └────────────────────┘
```

## 7. Ограничения и дальнейшие этапы развития

### Главные ограничения текущего ядра

- используется синтетический `HumanLikeEyeTracker`, а не настоящий eye-tracker;
- UI пока временный и консольный;
- velocity validation основан на простых эвристиках;
- нет обученного ML-классификатора;
- нет датасета реальных пользователей;
- не реализована защита от replay-атак и подмены gaze-данных;
- нет адаптации под разные устройства, камеры и частоты кадров;
- параметры пока подбираются вручную.

### Дальнейшие этапы развития

1. Подключить OpenCV / MediaPipe для реального gaze-tracking.
2. Сделать полноценный UI с визуальными стимулами.
3. Собрать датасет человеческих и ботоподобных траекторий.
4. Добавить ML-классификатор поверх признаков.
5. Реализовать server-side verification.
6. Добавить anti-replay и подпись сессий.
7. Ввести метрики качества: FAR, FRR, ROC-AUC, EER.

### Промпт для генерации изображения проблем

```text
A conceptual academic cybersecurity illustration showing limitations and future challenges of an eye-tracking CAPTCHA system: synthetic data, missing real camera tracking, noisy signals, replay attack risk, bot adversary, machine learning classifier roadmap. Dark navy background, warning accents in amber and red, cyan technical overlays, clean presentation style, no text, 16:9.
```

## 8. Итог

### Смысловой вывод

В проекте реализовано ядро интеллектуальной CAPTCHA, которое проверяет пользователя не по введённому ответу, а по динамике движения взгляда. Это создаёт основу для поведенческой защиты от автоматизированного прохождения.

Текущая версия является исследовательским прототипом: она уже содержит архитектуру, математическое ядро, симулятор человеческого взгляда, velocity analysis, scoring и session-level decision. Дальнейшее развитие может идти в сторону реального eye-tracking, ML-классификации и интеграции в web/security systems.

### Финальная мысль для защиты

> Чем сильнее развиваются нейросети и боты, тем больше внимания придётся уделять не только проверке результата действия, но и анализу самого поведения пользователя. Cognitive CAPTCHA — это шаг в сторону таких поведенческих систем безопасности.

### Промпт для итогового изображения

```text
A powerful futuristic cybersecurity presentation finale image: humans and AI bots in a digital world, increasing need to protect systems from neural network attacks and automated bots, glowing shield around secure systems, eye-tracking trajectories as behavioral security signals, dark navy background, cyan and violet highlights, dramatic but clean academic style, no text, 16:9.
```
