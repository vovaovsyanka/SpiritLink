# syntax=docker/dockerfile:1
#
# Образ бэкенда SpiritLink (FastAPI + общий BERT на процессоре).
#
# Многоэтапная сборка (multi-stage): в первой стадии ("builder") ставятся зависимости, там же остаются
# компиляторы и кэши pip. Во вторую стадию ("runtime") копируется только готовое окружение, поэтому
# итоговый образ меньше и в нём нет лишних инструментов (а значит и меньше уязвимостей для сканера Trivy).
#
# Что в образ НЕ входит и берётся снаружи (compose.yml подключает это томом):
#   /app/models  — веса BERT (1,6 ГБ, не публичные, в git не хранятся)
# Языковые модели в образе не нужны: на сервере они работают в LLM-сервисе (LLM_BACKEND=ollama).

# ── Стадия 1: зависимости ────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# PyTorch отдельным слоем и в CPU-сборке: у ВМ нет видеокарты, а обычная сборка с PyPI тянет CUDA (около 3 ГБ лишнего).
# Docker кэширует слои: пока requirements.txt не менялся, пересборка образа не качает всё заново.
RUN pip install "torch>=2.7" --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
# Строка --extra-index-url внутри requirements.txt нужна для установки на ПК; torch уже стоит, поэтому он не перекачивается
RUN pip install -r requirements.txt

# ── Стадия 2: то, что реально запускается ────────────────────────────────────
FROM python:3.11-slim AS runtime

# Не root: если в приложении найдут уязвимость, у взломщика не будет прав администратора в контейнере
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin app \
    && apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1

WORKDIR /app
# Только то, что нужно сервису (список исключений — в .dockerignore)
COPY --chown=app:app alembic.ini main.py ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app static ./static
COPY --chown=app:app docker/entrypoint.sh /entrypoint.sh
RUN chmod 0555 /entrypoint.sh && mkdir -p /app/logs && chown app:app /app/logs

USER app
EXPOSE 8000

# Контейнер "здоров", когда сервер принимает запросы и пайплайн (BERT + модели) загружен.
# Пока идёт загрузка (минуты), start-period не засчитывает неудачные проверки.
HEALTHCHECK --interval=15s --timeout=5s --start-period=300s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health | grep -q '"pipeline_ready":true' || exit 1

ENTRYPOINT ["/entrypoint.sh"]
