#!/bin/bash
# Быстрая проверка, что выложенный сервис жив:  deploy/smoke.sh http://127.0.0.1:8082
# Падает (код 1), если что-то не отвечает, и тем самым останавливает пайплайн.
set -euo pipefail
BASE="${1:?укажите адрес, например http://127.0.0.1:8082}"

fail() { echo "SMOKE: ОШИБКА — $1"; exit 1; }

# /health: пайплайн (BERT и модели) загружен. Даём до 5 минут: после старта модели ещё прогреваются.
for attempt in $(seq 1 60); do
    if curl -fsS "$BASE/health" 2>/dev/null | grep -q '"pipeline_ready":true'; then
        echo "SMOKE: /health — пайплайн готов"
        break
    fi
    [ "$attempt" -lt 60 ] || fail "/health не стал pipeline_ready за 5 минут"
    sleep 5
done

# Тело ответа сначала кладём в переменную, а не передаём через конвейер в grep -q: grep -q закрывает конвейер
# раньше времени, и curl с pipefail ложно считался бы упавшим.
get() { curl -fsS "$BASE$1" 2>/dev/null; }

if get /world-levels >/dev/null; then fail "/world-levels отвечает без токена"; fi        # должен требовать вход (401)
get /docs >/dev/null                                           || fail "нет документации Swagger (/docs)"
openapi="$(get /openapi.json)" && [[ "$openapi" == *'"/predict"'* ]] || fail "в openapi.json нет /predict"
page="$(get /)"               && [[ "$page" == *unity-container* ]]  || fail "главная страница не отдаёт игру"
config="$(get /StreamingAssets/config.json)" && [[ "$config" == *server_url* ]] || fail "нет config.json игры"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/metrics")" = "404" ] || fail "/metrics виден снаружи"
echo "SMOKE: всё в порядке ($BASE)"
