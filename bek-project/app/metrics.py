"""
Метрики Prometheus. Prometheus раз в 15 секунд читает GET /metrics и складывает числа во временный ряд,
Grafana рисует по ним графики (monitoring/ в корне репозитория).

Снаружи /metrics закрыт (nginx его не проксирует): его читает только Prometheus по внутренней сети docker.
"""

import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 30, 60)

HTTP_REQUESTS = Counter("http_requests_total", "HTTP-запросы", ["method", "path", "status"])
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "Время обработки HTTP-запроса", ["method", "path"], buckets=_LATENCY_BUCKETS
)
HTTP_IN_PROGRESS = Gauge("http_requests_in_progress", "HTTP-запросы в обработке прямо сейчас")

LLM_REQUESTS = Counter(
    "spiritlink_llm_requests_total", "Обращения к языковым моделям", ["model", "purpose", "result"]
)
LLM_DURATION = Histogram(
    "spiritlink_llm_duration_seconds", "Время ответа языковой модели", ["model", "purpose"], buckets=_LATENCY_BUCKETS
)
BERT_DURATION = Histogram("spiritlink_bert_duration_seconds", "Время работы общего BERT", buckets=_LATENCY_BUCKETS)
PREDICT_OUTCOMES = Counter(
    "spiritlink_predict_total", "Чем закончились запросы игроков в свободном промпте", ["outcome"]
)


def predict_outcome(passed: bool, record) -> str:
    """passed — введено слово; hygiene — отклонён до моделей; chat — болтовня; hint — подсказка шлюза; defender — дошёл до защитника."""
    if passed:
        return "passed"
    if record is None:
        return "hygiene"
    if not record.bert_dangerous:
        return "chat"
    return "defender" if record.category_match else "hint"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Считает запросы и время по шаблону пути (/passes/{pass_id}/start, а не по каждому pass_id отдельно)."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        HTTP_IN_PROGRESS.inc()
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            HTTP_IN_PROGRESS.dec()
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            HTTP_DURATION.labels(request.method, path).observe(time.perf_counter() - start)
