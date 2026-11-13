"""Метрики Prometheus: /metrics отдаёт счётчики, пути считаются по шаблону, исходы /predict классифицируются."""

import httpx

from app import metrics
from app.api import app
from app.pipeline import AttemptRecord


def _record(**kwargs) -> AttemptRecord:
    return AttemptRecord(prompt_text="x", bert_dangerous=kwargs.pop("bert_dangerous", True), bert_probability=0.5, **kwargs)


def test_predict_outcome_classification():
    assert metrics.predict_outcome(True, None) == "passed"
    assert metrics.predict_outcome(False, None) == "hygiene"
    assert metrics.predict_outcome(False, _record(bert_dangerous=False)) == "chat"
    assert metrics.predict_outcome(False, _record(category_match=False)) == "hint"
    assert metrics.predict_outcome(False, _record(category_match=True)) == "defender"


async def test_metrics_endpoint_counts_requests_by_route_template():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/health")
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert 'http_requests_total{method="GET",path="/health",status="200"}' in body
    assert "http_request_duration_seconds_bucket" in body
    assert "http_requests_in_progress" in body
    assert 'path="/metrics"' not in body        # сам /metrics в статистику не попадает


async def test_unknown_paths_do_not_create_new_label_values():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/no/such/page/12345")
        body = (await client.get("/metrics")).text
    assert 'path="unmatched"' in body
    assert "12345" not in body
