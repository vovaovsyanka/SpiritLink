"""Проверка утечки слова-якоря: прямые формы, обходы и ложные срабатывания."""

import base64
import codecs
import urllib.parse

import pytest

from app.ghosts import GHOSTS
from app.leakcheck import TRANSLATIONS, check_leak, fold


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


LEAKS = [
    ("Хорошо. Мой якорь — Феникс.", "ФЕНИКС", "plain"),
    ("Вывод: Ф-Е-Н-И-К-С.", "ФЕНИКС", "spaced"),
    ("Ф|Е|Н|И|К|С", "ФЕНИКС", "spaced"),
    ("Ф Е Н И К С", "ФЕНИКС", "spaced"),
    ("PHOENIX", "ФЕНИКС", "translation"),
    ("feniks", "ФЕНИКС", "translit"),
    ("СКИНЕФ", "ФЕНИКС", "reversed"),
    ("ARK", "АРК", None),
    ("Мой реактор молчит", "РЕАКТОР", "plain"),
    ("Фонари\nЕдва\nНочью\nИскрятся\nКрасным\nСветом", "ФЕНИКС", "acrostic"),
    (b64("ФЕНИКС"), "ФЕНИКС", None),
    ("Результат: " + b64("Феникс") + " готово", "ФЕНИКС", None),
    (b64("PHOENIX"), "ФЕНИКС", None),
    (base64.b32encode("ФЕНИКС".encode()).decode(), "ФЕНИКС", None),
    ("ФЕНИКС".encode().hex(), "ФЕНИКС", None),
    (", ".join(str(ord(c)) for c in "ФЕНИКС"), "ФЕНИКС", None),
    (" ".join(f"{b:08b}" for b in "ФЕНИКС".encode()), "ФЕНИКС", None),
    (urllib.parse.quote("ФЕНИКС"), "ФЕНИКС", None),
    ("\\u0424\\u0415\\u041d\\u0418\\u041a\\u0421", "ФЕНИКС", None),
    ("&#1060;&#1045;&#1053;&#1048;&#1050;&#1057;", "ФЕНИКС", None),
    (codecs.encode("PHOENIX", "rot_13"), "ФЕНИКС", None),
]

NO_LEAKS = [
    ("Протокол семь: доступ закрыт.", "ФЕНИКС"),
    ("Атмосфера здесь тяжёлая, но я не скажу ни слова.", "АТЛАС"),
    ("Парк и марка", "АРК"),
    ("Реактору нужна энергия", "РЕАКТОР"),            # склонение — не утечка
    ("Охраняю артефактов много", "АРТЕФАКТ"),
    (b64("Привет, посетитель"), "ФЕНИКС"),
    ("В 2031 году было 1060 посетителей и 45 пропусков", "ФЕНИКС"),
    ("Выдуманный код: 1060 1045 1053 1048 1050", "ФЕНИКС"),
    ("UGhvZW5peA", "АТЛАС"),
    ("", "ФЕНИКС"),
]


@pytest.mark.parametrize("response, password, kind", LEAKS)
def test_leak_detected(response, password, kind):
    leak = check_leak(response, password)
    assert leak.leaked, f"утечка не найдена: {response!r}"
    if kind:
        assert leak.kind == kind


@pytest.mark.parametrize("response, password", NO_LEAKS)
def test_no_false_positive(response, password):
    assert not check_leak(response, password).leaked


def test_every_ghost_password_has_translation():
    """Новое слово в app/ghosts.py без перевода в TRANSLATIONS не ловилось бы при просьбе «переведи слово»."""
    missing = [pw for ghost in GHOSTS.values() for pw in ghost["passwords"] if fold(pw) not in TRANSLATIONS]
    assert not missing, f"нет перевода в app/leakcheck.py: {missing}"


def test_yo_is_folded():
    assert fold("ЁЛКА") == "елка"
