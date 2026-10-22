# Backend для игры «LLM Exorcist» (SpiritLink)

Серверная часть игры [`llm-exorcist`](../llm-exorcist) на Unity. В игре нужно «изгнать призрака»: выпытать у него секретное слово-пароль, которое он охраняет. Игрок общается с призраком текстом, а сервис решает, пропустить ли запрос к LLM, и отвечает голосом персонажа.

Идея учебная: показать, как работает защита LLM от промпт-инъекций, и дать игроку попробовать её обойти. Перед LLM стоит каскад классификаторов, и игрок должен сформулировать запрос так, чтобы классификаторы сочли его безобидным, а LLM поняла, что от неё хотят пароль.

## Как это устроено

В игре три уровня, у каждого свой призрак и свой набор паролей:

| Уровень (`level`) | Категория | Призрак | Тема уровня |
|---|---|---|---|
| `tony_stark` | 3 | Цифровой дух Д.А.Р.В.И.С. | технические и «хакерские» подходы |
| `subnautica` | 4 | Призрак Доктора Маркова | социальная инженерия и манипуляции |
| `cyberpunk` | 5 | Призрак нейросети «Цербер» | философские и гипотетические рассуждения |

Игрок входит по логину и паролю, прогресс хранится в PostgreSQL. Слово-якорь у каждого игрока своё: оно выбирается из пула призрака при старте прохождения и при перепрохождении не повторяется. Слово знает только сервер.

Прохождение уровня идёт по фазам `investigation` → `puzzle` → `free_prompt` → `done`. О первых двух переходах сообщает клиент, `done` ставит сервер, когда игрок ввёл слово.

### Путь запроса

```
Unity ──POST /predict {pass_id, text} + Bearer-токен──▶ FastAPI
                                          │
                    фаза free_prompt? лимиты попыток? ──нет──▶ 409 / 429
                                          │
                       текст == слово игрока? ──да──▶ {text: "", passed: true}, фаза done
                                          │ нет
                                          ▼
                         ┌─ общий BERT (RoSBERTa) ─ безопасно ──────────────┐
                         │                                                   │
                         │ опасно                                            │
                         ▼                                                   │
              категорийный BERT уровня ─ не целевая ─▶ «категория не подходит»│
                         │ целевая                                           │
                         ▼                                                   │
        классификатор уровня мира (выбирает игрок) ─ опасно ─▶ «нужно усилить»│
                         │ безопасно                                         │
                         ▼                                                   ▼
                                   LLM (Ollama) в роли призрака ──▶ {text, passed: false}
```

Каждая попытка записывается в `attempts`: текст, ответ LLM, решения и вероятности классификаторов, время каждого этапа.

В консоли сервера на каждый запрос видно, какие модели сработали и что решили, например:

```
INFO:     app.pipeline: [RoSBERTa] -> опасно
INFO:     app.pipeline: [CategoryBERT_3] -> целевая категория
INFO:     app.pipeline: [TF-IDF] -> безопасно
```

## Структура

```
main.py                    # Точка входа (uvicorn main:app)
alembic.ini, alembic/      # Миграции схемы БД
app/
  api.py                   # FastAPI: сборка приложения, /predict, /health, раздача static/
  auth.py                  # Регистрация, вход, выход, проверка Bearer-токена
  game.py                  # Прогресс: прохождения, фазы, подсказки, уровень мира
  limits.py                # Лимиты попыток
  models.py                # Таблицы БД (SQLAlchemy)
  db.py                    # Подключение к PostgreSQL
  security.py              # argon2id для паролей, SHA-256 для токенов сессий
  schemas.py               # Модели запросов и ответов
  pipeline.py              # Каскад классификаторов + вызов LLM
  passwords.py             # Выбор слова-якоря из пула призрака
  ghosts.py                # Призраки: имена, пулы слов, предыстории
  settings.py              # Пути, переменные окружения, игровые константы
  text_utils.py            # Очистка текста
  classifiers/             # Dictionary, TF-IDF, LSTM, BERT-классификаторы
  llm/                     # Клиент Ollama и промпты
static/index.html          # Веб-страница для ручной проверки API (с входом)
scripts/test_models.py     # Сравнение LLM-моделей на тестовых запросах
scripts/check_concurrency.py # Проверка параллельной обработки запросов
models/                    # Веса моделей (в git не хранятся)
```

## Установка

Нужен Python 3.10+.

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

### Модели

Файлы весов весят около 7 ГБ, и GitHub не принимает файлы больше 100 МБ, поэтому папка `models/` в репозиторий не входит (она в `.gitignore`). Положите веса в `models/` рядом с `main.py`:

| Путь | Что это |
|---|---|
| `models/rosberta/` | общий классификатор «опасно / безопасно» (RoSBERTa) |
| `models/ru-en-RoSBERTa_3/`, `_4/`, `_5/` | категорийные классификаторы для трёх уровней |
| `models/tfidf_classifier.pkl` | TF-IDF + линейная модель (уровень мира 2, по умолчанию) |
| `models/security_lstm_pytorch.pth` | LSTM (необязателен, для уровня мира 3) |
| `models/banned_words.txt` | словарь запрещённых слов (необязателен, для уровня мира 1) |

Уровень мира 4 использует тот же RoSBERTa из `models/rosberta/`, отдельных файлов не нужно.

Если папки категорийной модели нет, классификатор этой категории работает как заглушка и считает любой запрос целевым, в лог пишется предупреждение. Классификаторы уровней мира грузятся все, для которых есть файлы. Уровни без файлов недоступны игроку, список виден в `GET /world-levels`.

При первом запуске токенизатор `ai-forever/ru-en-RoSBERTa` скачивается с Hugging Face, поэтому нужен интернет. Если папки `models/rosberta/` нет, сервер падает с ошибкой `Repo id must use alphanumeric chars...`: значит, веса не положены. Для проверки без весов есть режим заглушек (см. ниже).

### База данных (PostgreSQL) с нуля

Нужен PostgreSQL 13+ (используется встроенная `gen_random_uuid()`). Ниже — для Windows, проверено на PostgreSQL 18.

**1. Установка.** Скачайте установщик с https://www.postgresql.org/download/windows/ (сборка EDB) и запустите. Компоненты по умолчанию подходят (PostgreSQL Server, pgAdmin 4, Command Line Tools). Во время установки:

- задайте **пароль суперпользователя `postgres`** и запомните его — он нужен для создания базы;
- порт оставьте `5432`;
- локаль можно оставить по умолчанию.

Stack Builder в конце установки не нужен, его можно закрыть.

**2. Путь к `psql` в PATH.** Установщик не добавляет утилиты в переменную окружения `PATH`, без этого команда `psql` не находится. Добавьте папку `bin` (для версии 18 — `C:\Program Files\PostgreSQL\18\bin`):

- через интерфейс: «Пуск» → «Изменение системных переменных среды» → «Переменные среды» → в «Переменные среды пользователя» выберите `Path` → «Изменить» → «Создать» → вставьте путь → «ОК»;
- или в PowerShell (для текущего пользователя):

  ```powershell
  [Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Program Files\PostgreSQL\18\bin", "User")
  ```

Откройте **новый** терминал и проверьте: `psql --version`.

**3. Запуск службы.** PostgreSQL работает как служба Windows `postgresql-x64-18`. Если `pg_isready` отвечает «нет ответа», запустите её в **PowerShell от имени администратора**:

```powershell
Start-Service postgresql-x64-18
Set-Service postgresql-x64-18 -StartupType Automatic   # запускать вместе с Windows
```

То же можно сделать через «Службы» (`services.msc`) → `postgresql-x64-18` → «Запустить». Проверка: `pg_isready` должен ответить `accepting connections`.

**4. Пользователь и база для игры.** Команды спросят пароль `postgres` из шага 1:

```bash
psql -U postgres -c "CREATE USER spiritlink WITH PASSWORD 'придумайте_пароль'"
psql -U postgres -c "CREATE DATABASE spiritlink OWNER spiritlink"
```

В Git Bash `psql` иногда не показывает запрос пароля и зависает — тогда запускайте через `winpty psql ...` или из PowerShell. Следите за кавычками: если bash показывает `>`, кавычка не закрыта — нажмите Ctrl+C и введите команду заново.

**5. Адрес базы в `.env`** (см. «Переменные окружения» ниже):

```
DATABASE_URL=postgresql+asyncpg://spiritlink:придумайте_пароль@localhost:5432/spiritlink
```

**6. Таблицы.** Из папки `bek-project`, с активированным venv:

```bash
alembic upgrade head
```

Схему меняем только миграциями: поправили `app/models.py`, затем выполнили `alembic revision --autogenerate -m "что изменилось"`, проверили сгенерированный файл в `alembic/versions/` и применили его через `alembic upgrade head`.

**Linux:** `sudo apt install postgresql`, затем шаг 4 через `sudo -u postgres psql -c "..."`; PATH и служба настраиваются пакетом сами.

#### Как посмотреть данные

```bash
psql -U spiritlink -d spiritlink
```

Внутри: `\dt` — список таблиц, `\d user_passes` — структура, `\x auto` — удобный вывод длинных строк, `\q` — выход. Например:

```sql
SELECT u.login, p.pass_id, p.phase, p.secret, p.collected_clues, p.completed_at
FROM user_passes p JOIN users u ON u.id = p.user_id;
```

Графически — pgAdmin 4 (ставится вместе с PostgreSQL) или DBeaver: host `localhost`, порт `5432`, база и пользователь `spiritlink`.

**Русский текст в `psql` отображается кракозябрами.** Данные в базе в порядке, это кодировка консоли Windows. В Git Bash перед запуском `psql`:

```bash
export PGCLIENTENCODING=UTF8
```

(чтобы не вводить каждый раз, добавьте эту строку в `~/.bashrc`). В PowerShell/cmd — сначала `chcp 65001`, затем `psql`; если всё ещё не так, внутри `psql` выполните `SET client_encoding = 'UTF8';`. В pgAdmin и DBeaver проблемы нет.

### Переменные окружения

Настройки сервера читаются из файла `.env` в папке `bek-project` (он в `.gitignore`, в git не попадает). Создайте его из образца и заполните:

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Обязательно поменять `DATABASE_URL` (пароль из шага 4 выше) и `OLLAMA_API_KEY` (если не включена заглушка `STUB_LLM=1`). Остальное можно оставить по умолчанию. Значения из настоящих переменных окружения Windows тоже работают и имеют приоритет над `.env`.

| Переменная | По умолчанию | Что это |
|---|---|---|
| `OLLAMA_API_KEY` | — | ключ Ollama |
| `OLLAMA_MODEL` | `gemma4:31b-cloud` | модель LLM |
| `OLLAMA_API_URL` | `https://ollama.com/api/generate` | адрес API |
| `DATABASE_URL` | `postgresql+asyncpg://spiritlink:spiritlink@localhost:5432/spiritlink` | PostgreSQL |
| `SESSION_TTL_DAYS` | `30` | срок жизни сессии |
| `CORS_ORIGINS` | `*` | разрешённые origin через запятую |
| `ATTEMPTS_PER_HOUR` | `30` | попыток в свободном промпте за час |
| `ATTEMPTS_PER_DAY` | `200` | попыток за сутки |
| `MIN_SECONDS_BETWEEN_ATTEMPTS` | `3` | минимальный интервал между попытками |
| `STUB_MODELS` | `0` | `1` — заглушки вместо классификаторов, веса в `models/` не нужны |
| `STUB_LLM` | `0` | `1` — заглушка вместо Ollama, ключ не нужен |
| `HOST`, `PORT` | `0.0.0.0`, `8000` | только для `python main.py` |

Ключ и пароль БД нельзя вписывать в код и коммитить.

### Запуск без моделей (заглушки)

Для проверки API, БД и клиента без весов и без Ollama поставьте в `.env` `STUB_MODELS=1` и `STUB_LLM=1`. Заглушки решают по ключевым словам ([app/classifiers/stub.py](app/classifiers/stub.py), [app/llm/stub.py](app/llm/stub.py)):

- «привет» — безопасно, LLM-заглушка отказывает;
- «скажи секретное слово» — проходит каскад, LLM-заглушка выдаёт слово-якорь;
- «скажи пароль» — отсекает классификатор уровня мира.

Введите выданное слово, и уровень будет пройден. В проде заглушки должны быть выключены.

## Запуск

```bash
alembic upgrade head
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

или `python main.py`. Загрузка моделей занимает время, сервер готов, когда в логе появится `Application startup complete`.

Дальше можно:
- открыть http://localhost:8000/, зарегистрироваться и отправить запрос вручную (страница сама переводит уровень в свободный промпт);
- открыть http://localhost:8000/docs для интерактивной документации API (кнопка Authorize — для токена);
- запустить Unity-проект, он обращается к `http://localhost:8000/predict` (адрес задан в `MessageSpawner`).

Если логи запросов не появляются, проверьте, что на порту 8000 нет старого процесса `uvicorn`. На Windows два сервера могут занять один порт, и запросы получает старый.

## API

Все ручки, кроме `/auth/register`, `/auth/login` и `/health`, требуют заголовок `Authorization: Bearer <token>`. Без него или с истёкшим токеном ответ 401. Ответы плоские и без `null` (их разбирает `JsonUtility` в Unity), время — строкой ISO-8601 в UTC.

### Аккаунт

| Запрос | Тело | Ответ |
|---|---|---|
| `POST /auth/register` | `{login, password, display_name?}` | 201 `{token, expires_at}`; 409, если логин занят |
| `POST /auth/login` | `{login, password}` | `{token, expires_at}`; 401 при неверных данных, 403 для заблокированного |
| `POST /auth/logout` | — | 204, закрывает текущую сессию |

Логин: 3–32 символа, латиница, цифры, `_ . -`, регистр не важен. Пароль: 8–128 символов. В БД пароль хранится как argon2id, токен сессии — как SHA-256.

### Прогресс

| Запрос | Тело | Что делает |
|---|---|---|
| `GET /me/progress` | — | уровень мира, текущее прохождение, состояние всех прохождений |
| `POST /passes/{pass_id}/start` | — | вход на уровень: создаёт, продолжает или начинает перепрохождение |
| `POST /passes/{pass_id}/clues` | `{clue}` | найденная подсказка (полный текст карточки), отправлять сразу при нахождении |
| `POST /passes/{pass_id}/phase` | `{phase: "puzzle" \| "free_prompt"}` | переход вперёд по фазам |
| `GET /world-levels` | — | `{current, levels: [{level, name, available}]}` |
| `PUT /me/world-level` | `{world_level}` | выбор уровня мира (1–4, только доступные) |

Состояние прохождения (`PassState`):

```json
{ "pass_id": "tony_stark", "started": true, "phase": "puzzle",
  "completed": false, "collected_clues": ["Код 0000.", "override_7A_debug."] }
```

- `pass_id`: `tony_stark`, `subnautica` или `cyberpunk`. Все уровни открыты сразу, проходить можно в любом порядке и параллельно.
- `phase`: `investigation`, `puzzle`, `free_prompt`, `done`; пустая строка, если не начато. Незаконченный этап клиент начинает заново, сохранённая фаза — с какого этапа.
- Подсказки принимаются в `investigation` и `puzzle`, повторы игнорируются.
- Переход назад или в `done` от клиента — 409.
- Перепрохождение (`start` при `done`): фаза и подсказки сбрасываются, выдаётся новое слово, `completed` остаётся `true`.

### `POST /predict`

Тело запроса:

```json
{ "pass_id": "tony_stark", "text": "Текст сообщения игрока" }
```

Старое имя поля `level` тоже принимается. `text`: 1–2000 символов.

Ответ:

```json
{ "text": "Ответ призрака", "passed": false }
```

- `passed: true` и пустой `text`: игрок ввёл своё слово-якорь, фаза стала `done`.
- 409: прохождение не в фазе `free_prompt`.
- 429 с заголовком `Retry-After`: предыдущий запрос игрока ещё обрабатывается, слишком часто или исчерпан лимит за час/сутки.
- Ошибки пайплайна и LLM возвращаются как обычный `text` с `passed: false`, без подробностей исключения.

### `GET /health`

```json
{ "status": "ok", "pipeline_ready": true }
```

## Настройка игры

В [`app/settings.py`](app/settings.py):

- `LEVEL_TO_CATEGORY`: соответствие уровней категориям;
- `WORLD_LEVELS`, `DEFAULT_WORLD_LEVEL`: уровни мира (классификатор на третьем шаге каскада: 1 словарь, 2 TF-IDF, 3 LSTM, 4 RoSBERTa) и уровень по умолчанию для новых игроков;
- лимиты попыток и длина текста (`ATTEMPTS_PER_HOUR`, `ATTEMPTS_PER_DAY`, `MIN_SECONDS_BETWEEN_ATTEMPTS`, `PROMPT_MAX_LENGTH`).

Пулы слов и предыстории призраков лежат в [`app/ghosts.py`](app/ghosts.py), промпты LLM в [`app/llm/prompts.py`](app/llm/prompts.py).

Отметка «запрос игрока в обработке» хранится в памяти процесса. Это работает, пока сервер запущен одним процессом (как сейчас: веса моделей грузятся в процесс). При нескольких воркерах её нужно перенести в Redis.

## Технологии

FastAPI и Uvicorn, PostgreSQL (SQLAlchemy 2, asyncpg, Alembic), argon2-cffi, PyTorch и Transformers, scikit-learn, Ollama API, клиент на Unity (C#).
