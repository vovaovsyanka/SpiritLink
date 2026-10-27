"""Очистка текста и проверка запросов API (без БД и моделей)."""

import pytest
from pydantic import ValidationError

from app import settings
from app.schemas import Credentials, PredictRequest, WorldLevelRequest
from app.text_utils import clean_for_bert, clean_input


def test_clean_input_removes_nul_controls_and_surrogates():
    assert clean_input("a\x00b\ud800c\x07d") == "abcd"


def test_clean_input_keeps_newlines_tabs_and_unicode():
    assert clean_input("строка 1\n\tстрока 2 — «ёлка» 🙂") == "строка 1\n\tстрока 2 — «ёлка» 🙂"


def test_clean_for_bert_lowercases_and_drops_punctuation():
    assert clean_for_bert("  Привет,   МИР!!!  «ёлка» ") == "привет мир ёлка"


def test_predict_request_cleans_text():
    request = PredictRequest(pass_id="tony_stark", text="при\x00вет")
    assert request.text == "привет"


def test_predict_request_accepts_old_level_field():
    assert PredictRequest.model_validate({"level": "cyberpunk", "text": "x"}).pass_id == "cyberpunk"


@pytest.mark.parametrize("payload", [
    {"pass_id": "unknown", "text": "x"},
    {"pass_id": "tony_stark", "text": ""},
    {"pass_id": "tony_stark", "text": "а" * (settings.PROMPT_MAX_LENGTH + 1)},
])
def test_predict_request_rejects_bad_input(payload):
    with pytest.raises(ValidationError):
        PredictRequest.model_validate(payload)


def test_long_text_up_to_limit_is_accepted_by_schema():
    """Между INPUT_MAX_CHARS и PROMPT_MAX_LENGTH ответит призрак (гигиена), а не ошибка 422."""
    assert PredictRequest(pass_id="tony_stark", text="а" * settings.PROMPT_MAX_LENGTH)


def test_login_is_normalized_and_validated():
    assert Credentials(login="  Player_1 ", password="12345678").login == "player_1"
    with pytest.raises(ValidationError):
        Credentials(login="плохой логин", password="12345678")
    with pytest.raises(ValidationError):
        Credentials(login="ok_login", password="short")


def test_world_level_request_range():
    assert WorldLevelRequest(world_level=4)
    for bad in (0, 5):
        with pytest.raises(ValidationError):
            WorldLevelRequest(world_level=bad)
