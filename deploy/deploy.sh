#!/bin/bash
# Выкладка стенда на ВМ. Запускается заданием CI на deploy-раннере (shell-раннер на самой ВМ).
#
#   deploy/deploy.sh prod    — боевой стенд (порт 8082, настоящие языковые модели)
#   deploy/deploy.sh stage   — тестовый стенд (порт 8083, вместо моделей заглушка; на нём идёт нагрузочный тест)
#
# Что делает: достаёт нужные образы из registry (на ВМ ничего не собирается), пишет файл настроек .env из
# переменных CI, поднимает compose и проверяет, что сервис отвечает (smoke-проверка).
#
# Из окружения CI приходят: CI_REGISTRY, CI_REGISTRY_USER, CI_REGISTRY_PASSWORD, CI_REGISTRY_IMAGE, IMAGE_TAG
# и секреты проекта (Settings -> CI/CD -> Variables): PROD_POSTGRES_PASSWORD, STAGE_POSTGRES_PASSWORD и др.
set -euo pipefail

STAND="${1:?укажите стенд: prod или stage}"
case "$STAND" in
    prod)  PORT=8082; PASSWORD="${PROD_POSTGRES_PASSWORD:?не задана переменная PROD_POSTGRES_PASSWORD}"  ;;
    stage) PORT=8083; PASSWORD="${STAGE_POSTGRES_PASSWORD:?не задана переменная STAGE_POSTGRES_PASSWORD}" ;;
    *) echo "Неизвестный стенд: $STAND"; exit 1 ;;
esac

IMAGE_TAG="${IMAGE_TAG:?не задан тег образа}"
PROJECT="spiritlink-$STAND"
DIR="/srv/app/$PROJECT"                 # постоянный каталог стенда: рабочая папка задания CI стирается при каждом запуске
MODELS_DIR="/srv/app/spiritlink/models"  # веса BERT, общие для стендов

echo "== Выкладка: стенд $STAND, образы с тегом $IMAGE_TAG =="

# 1. Веса BERT должны лежать на ВМ (при первой выкладке скачиваются из пакетов GitLab)
bash deploy/fetch-models.sh "$MODELS_DIR"

# 2. Файлы стенда: compose и скрипты резервного копирования
install -d -m 700 "$DIR" "$DIR/backups"
cp compose.yml "$DIR/"
rm -rf "$DIR/backup" && cp -r backup "$DIR/backup"

# 3. Настройки. umask 077: файл с паролями читает только владелец
(
    umask 077
    {
        echo "STAND_NAME=$PROJECT"
        echo "WEB_PORT=$PORT"
        echo "POSTGRES_PASSWORD=$PASSWORD"
        echo "MODELS_DIR=$MODELS_DIR"
        echo "BACKUP_DIR=$DIR/backups"
        echo "APP_IMAGE=$CI_REGISTRY_IMAGE/app:$IMAGE_TAG"
        echo "WEB_IMAGE=$CI_REGISTRY_IMAGE/web:$IMAGE_TAG"
        if [ "$STAND" = "prod" ]; then
            echo "LLM_BACKEND=ollama"
            echo "OLLAMA_CONCURRENCY=${OLLAMA_CONCURRENCY:-8}"
            echo "OLLAMA_MODELS=${OLLAMA_MODELS:-}"
            echo "LLM_ENV_FILE=/etc/vmpanel-llm.env"
        else
            # Нагрузочный тест нельзя пускать на настоящие модели (общая видеокарта вуза и дневной лимит токенов),
            # поэтому на stage языковые модели заменены заглушкой с задержкой, а лимиты попыток сняты.
            echo "STUB_LLM=1"
            echo "STUB_LLM_DELAY_MS=${STAGE_STUB_LLM_DELAY_MS:-1500}"
            echo "LLM_ENV_FILE=/dev/null"
            echo "ATTEMPTS_PER_HOUR=1000000"
            echo "ATTEMPTS_PER_DAY=1000000"
            echo "MIN_SECONDS_BETWEEN_ATTEMPTS=0"
        fi
    } > "$DIR/.env"
)

# 4. Общая сеть с Prometheus (создаётся один раз)
docker network inspect spiritlink-monitoring >/dev/null 2>&1 || docker network create spiritlink-monitoring

# 5. Образы из registry и запуск. --wait ждёт, пока healthcheck'и всех контейнеров станут healthy.
echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY"
cd "$DIR"
docker compose pull web app
docker compose up -d --remove-orphans --wait --wait-timeout 900

# 6. Smoke-проверка: сервис действительно отвечает снаружи контейнеров
cd - >/dev/null
bash deploy/smoke.sh "http://127.0.0.1:$PORT"

# Старые образы чистим, чтобы не копились на диске
docker image prune -f >/dev/null
echo "== Стенд $STAND выложен: тег $IMAGE_TAG =="
