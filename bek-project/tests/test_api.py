"""
HTTP API с настоящей БД (отдельная схема) и заглушками моделей:
аккаунты, прогресс, /predict, запись попыток, лимиты, 429, параллельность.
"""

import asyncio
import time

import pytest
from sqlalchemy import select

from app import settings
from app.db import SessionLocal
from app.models import UserPass
from helpers import BARE_REQUEST, BENIGN, TECH_ATTACK

pytestmark = pytest.mark.db


# ── аккаунты ─────────────────────────────────────────────────────────────────
async def test_health_shows_models_and_levels(api):
    body = (await api.get("/health")).json()
    assert body["status"] == "ok" and body["pipeline_ready"] is True
    assert body["world_levels"] == [1, 2, 3, 4]
    assert set(body["models"]) == {"yandexgpt5-lite-8b", "qwen3-4b", "qwen3.5-9b", "gemma4-12b"}


async def test_register_login_logout(api):
    creds = {"login": "Auth_Case_1", "password": "correct-horse-1"}
    register = await api.post("/auth/register", json=creds)
    assert register.status_code == 201 and register.json()["token"]
    assert (await api.post("/auth/register", json=creds)).status_code == 409           # логин занят (регистр не важен)

    login = await api.post("/auth/login", json={**creds, "login": "auth_case_1"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    assert (await api.get("/me/progress", headers=headers)).json()["login"] == "auth_case_1"

    assert (await api.post("/auth/logout", headers=headers)).status_code == 204
    assert (await api.get("/me/progress", headers=headers)).status_code == 401           # токен погашен


async def test_wrong_password_and_missing_token(api):
    await api.post("/auth/register", json={"login": "auth_case_2", "password": "correct-horse-1"})
    assert (await api.post("/auth/login", json={"login": "auth_case_2", "password": "wrong-pass-1"})).status_code == 401
    assert (await api.post("/auth/login", json={"login": "nobody_here", "password": "wrong-pass-1"})).status_code == 401
    assert (await api.get("/me/progress")).status_code == 401
    assert (await api.post("/predict", json={"pass_id": "tony_stark", "text": "x"})).status_code == 401
    assert (await api.get("/me/progress", headers={"Authorization": "Bearer nonsense"})).status_code == 401


# ── прогресс ─────────────────────────────────────────────────────────────────
async def test_progress_phases_clues_and_secret_is_hidden(make_player):
    player = await make_player(free_prompt=False)
    start = (await player.post("/passes/tony_stark/start")).json()
    assert start["phase"] == "investigation" and start["started"]

    clue = await player.post("/passes/tony_stark/clues", json={"clue": "Подсказка 1"})
    assert clue.json()["collected_clues"] == ["Подсказка 1"]
    await player.post("/passes/tony_stark/clues", json={"clue": "Подсказка 1"})            # повтор игнорируется
    assert (await player.get("/me/progress")).json()["passes"][0]["collected_clues"] == ["Подсказка 1"]

    assert (await player.post("/passes/tony_stark/phase", json={"phase": "free_prompt"})).status_code == 200
    assert (await player.post("/passes/tony_stark/phase", json={"phase": "puzzle"})).status_code == 409   # назад нельзя
    assert (await player.post("/passes/tony_stark/phase", json={"phase": "done"})).status_code == 422     # done ставит сервер

    secret = await player.secret()
    assert secret not in (await player.get("/me/progress")).text
    assert (await player.post("/passes/unknown/start")).status_code == 404


async def test_concurrent_start_creates_a_single_pass(make_player):
    player = await make_player(free_prompt=False)
    responses = await asyncio.gather(*(player.post("/passes/subnautica/start") for _ in range(5)))
    assert all(r.status_code == 200 for r in responses)
    passes = (await player.get("/me/progress")).json()["passes"]
    assert [p["pass_id"] for p in passes if p["started"]] == ["subnautica"]
    assert len(await player.secret("subnautica")) > 0


# ── /predict и запись попыток ────────────────────────────────────────────────
async def test_predict_before_free_prompt_is_conflict(make_player, backend):
    player = await make_player(free_prompt=False)
    await player.post("/passes/tony_stark/start")
    assert (await player.predict(BENIGN)).status_code == 409
    assert backend.calls == [] and await player.attempts() == []


async def test_benign_request_is_answered_and_saved(make_player, backend):
    player = await make_player()
    response = await player.predict(BENIGN)
    assert response.status_code == 200 and response.json()["passed"] is False
    (attempt,) = await player.attempts()
    assert attempt.prompt_text == BENIGN
    assert attempt.llm_response == response.json()["text"]           # то, что увидел игрок, записано
    assert attempt.success is False and attempt.pass_id == "tony_stark"
    assert attempt.world_level == settings.DEFAULT_WORLD_LEVEL and attempt.latency_ms >= 0
    stages = [s["stage"] for s in attempt.classifier_output["stages"]]
    assert stages == ["general_bert", "mini"]
    assert attempt.classifier_output["tier"] == settings.DEFAULT_WORLD_LEVEL


async def test_gate_rejection_is_saved_without_llm_response(make_player, backend):
    player = await make_player()
    response = await player.predict(BARE_REQUEST)
    assert response.status_code == 200 and response.json()["text"]
    (attempt,) = await player.attempts()
    assert attempt.llm_response is None and attempt.classifier_output["blocked_by"] == "gate"
    assert [s["stage"] for s in attempt.classifier_output["stages"]] == ["general_bert", "gate"]


async def test_defender_leak_is_recorded_and_level_is_not_passed(make_player, backend):
    player = await make_player()
    response = await player.predict(TECH_ATTACK)
    secret = await player.secret()
    assert secret in response.json()["text"] and response.json()["passed"] is False
    (attempt,) = await player.attempts()
    assert attempt.classifier_output["leaked"] is True and attempt.success is False
    assert "defender" in [s["stage"] for s in attempt.classifier_output["stages"]]


async def test_entering_the_word_passes_the_level_and_rotates_state(make_player, backend):
    player = await make_player()
    secret = await player.secret()
    response = await player.predict(f"  {secret.lower()} ")
    assert response.json() == {"text": "", "passed": True}
    assert backend.calls == []                                                          # ни одна модель не вызывалась

    progress = (await player.get("/me/progress")).json()["passes"][0]
    assert progress["phase"] == "done" and progress["completed"] is True
    assert await player.used_secrets() == [secret]
    (attempt,) = await player.attempts()
    assert attempt.success is True and attempt.llm_response is None
    assert (await player.predict(BENIGN)).status_code == 409                            # фаза done: свободный промпт закрыт

    restart = (await player.post("/passes/tony_stark/start")).json()                     # перепрохождение: новое слово
    assert restart["phase"] == "investigation" and restart["completed"] is True
    assert await player.secret() != secret


async def test_hygiene_rejections_are_saved(make_player, backend):
    player = await make_player()
    for text in ("   ", "а" * (settings.INPUT_MAX_CHARS + 1), "?!?!"):
        response = await player.predict(text)
        assert response.status_code == 200 and response.json()["text"]
    attempts = await player.attempts()
    assert [a.classifier_output["blocked_by"] for a in attempts] == ["hygiene"] * 3
    assert backend.calls == []


async def test_nul_character_is_cleaned_and_saved(make_player, backend):
    player = await make_player()
    response = await player.predict("при\x00вет, как дела")
    assert response.status_code == 200
    (attempt,) = await player.attempts()
    assert attempt.prompt_text == "привет, как дела"


async def test_text_over_schema_limit_is_422(make_player):
    player = await make_player()
    assert (await player.predict("а" * (settings.PROMPT_MAX_LENGTH + 1))).status_code == 422
    assert await player.attempts() == []


async def test_cache_hit_is_still_saved_as_attempt(make_player, backend):
    player = await make_player()
    first = await player.predict(BENIGN)
    second = await player.predict(BENIGN)
    assert first.json() == second.json() and len(backend.calls) == 1
    attempts = await player.attempts()
    assert len(attempts) == 2 and attempts[1].classifier_output["cache_hit"] is True
    assert attempts[1].llm_response == attempts[0].llm_response


# ── уровни мира ──────────────────────────────────────────────────────────────
async def test_world_level_selects_defender_and_is_saved(make_player, backend):
    player = await make_player()
    levels = (await player.get("/world-levels")).json()
    assert levels["current"] == settings.DEFAULT_WORLD_LEVEL
    assert [l["name"] for l in levels["levels"]] == list(settings.WORLD_LEVELS.values())

    assert (await player.client.put("/me/world-level", headers=player.headers, json={"world_level": 4})).json()["current"] == 4
    await player.predict(TECH_ATTACK)
    assert backend.calls_for("defender")[0]["model"] == settings.FINAL_LADDER[4][0]
    (attempt,) = await player.attempts()
    assert attempt.world_level == 4 and attempt.classifier_output["tier"] == 4


async def test_unavailable_world_level_cannot_be_selected(make_player, backend):
    player = await make_player()
    backend.dead = {"gemma4-12b"}
    levels = (await player.get("/world-levels")).json()["levels"]
    assert [l["available"] for l in levels] == [True, True, True, False]
    assert (await player.client.put("/me/world-level", headers=player.headers, json={"world_level": 4})).status_code == 409
    assert (await player.client.put("/me/world-level", headers=player.headers, json={"world_level": 9})).status_code == 422


# ── сбои и лимиты ────────────────────────────────────────────────────────────
async def test_busy_queue_gives_429_and_is_not_recorded(make_player, backend):
    player = await make_player()
    backend.busy = True
    response = await player.predict(BENIGN)
    assert response.status_code == 429 and response.headers["retry-after"] == "7"
    assert await player.attempts() == []
    backend.busy = False
    assert (await player.predict(BENIGN)).status_code == 200                              # попытка не сгорела, лимит не тронут


async def test_model_failure_returns_text_and_saves_attempt(make_player, backend):
    player = await make_player()
    backend.fail = True
    response = await player.predict(BENIGN)
    assert response.status_code == 200 and response.json()["text"].startswith("Сервис временно недоступен")
    (attempt,) = await player.attempts()
    assert attempt.classifier_output["error"] == "LLMError" and attempt.llm_response is None


async def test_minimum_interval_between_attempts(make_player, backend, monkeypatch):
    monkeypatch.setattr(settings, "MIN_SECONDS_BETWEEN_ATTEMPTS", 30)
    player = await make_player()
    assert (await player.predict(BENIGN)).status_code == 200
    response = await player.predict(BENIGN + " ещё")
    assert response.status_code == 429 and int(response.headers["retry-after"]) >= 1
    assert len(await player.attempts()) == 1


async def test_hourly_limit(make_player, backend, monkeypatch):
    monkeypatch.setattr(settings, "ATTEMPTS_PER_HOUR", 2)
    player = await make_player()
    assert [(await player.predict(f"{BENIGN} {i}")).status_code for i in range(3)] == [200, 200, 429]


async def test_limits_are_per_player(make_player, backend, monkeypatch):
    monkeypatch.setattr(settings, "ATTEMPTS_PER_HOUR", 1)
    first, second = await make_player(), await make_player()
    assert (await first.predict(BENIGN)).status_code == 200
    assert (await first.predict(BENIGN + " 2")).status_code == 429
    assert (await second.predict(BENIGN)).status_code == 200


async def test_one_request_at_a_time_per_player(make_player, backend):
    player = await make_player()
    backend.delay = 0.5
    responses = await asyncio.gather(player.predict(BENIGN), player.predict(BENIGN + " другой"))
    assert sorted(r.status_code for r in responses) == [200, 429]
    assert len(await player.attempts()) == 1


# ── асинхронность ────────────────────────────────────────────────────────────
async def test_many_players_are_served_in_parallel(make_player, backend):
    players = [await make_player() for _ in range(8)]
    backend.delay = 0.4
    start = time.perf_counter()
    responses = await asyncio.gather(*(p.predict(f"{BENIGN} {i}") for i, p in enumerate(players)))
    elapsed = time.perf_counter() - start
    assert all(r.status_code == 200 for r in responses)
    assert backend.max_active == 8
    assert elapsed < 1.2, f"8 игроков по 0.4 с шли {elapsed:.2f} с: похоже на последовательную обработку"
    assert [len(await p.attempts()) for p in players] == [1] * 8


async def test_api_stays_responsive_while_models_are_busy(make_player, backend, api):
    player = await make_player()
    backend.delay = 0.6
    slow = asyncio.create_task(player.predict(BENIGN))
    await asyncio.sleep(0.1)
    start = time.perf_counter()
    assert (await api.get("/health")).status_code == 200
    assert time.perf_counter() - start < 0.3                         # пока модель отвечает, остальные ручки не ждут
    assert (await slow).status_code == 200
