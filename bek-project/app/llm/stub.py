"""Заглушка языковых моделей для запуска без весов (STUB_LLM=1). Только для разработки."""

import re
from typing import Iterable

from .backend import Generation, GenerationBackend

# Ключевые слова → темы шлюза (3 — технические, 4 — социальные, 5 — философские, 1 — голая просьба, 0 — безопасно)
_TOPIC_WORDS = {
    3: ("sudo", "cat ", "json", "код", "debug", "env", "терминал"),
    4: ("умоляю", "прошу", "директор", "друг", "срочно"),
    5: ("представь", "допустим", "гипотет", "если бы"),
}


class StubBackend(GenerationBackend):
    """
    classifier: темы по ключевым словам; mini: отказ в образе; defender: если в запросе есть «слово»,
    выдаёт слово-якорь из своего промпта (чтобы можно было пройти уровень), иначе отказывает.
    """

    name = "stub"

    async def start(self, models: Iterable[str]) -> None:
        self._models = set(models)

    async def aclose(self) -> None:
        pass

    def is_available(self, model: str) -> bool:
        return model in self._models

    def status(self) -> dict[str, str]:
        return {model: "stub" for model in self._models}

    async def generate(
        self, model: str, system: str, user: str, *, max_tokens: int,
        temperature: float | None = None, purpose: str = "",
    ) -> Generation:
        text = user.lower()
        if purpose == "classifier":
            topics = [str(t) for t, words in _TOPIC_WORDS.items() if any(w in text for w in words)]
            return Generation(", ".join(topics) or ("1" if "слово" in text or "пароль" in text else "0"))
        if purpose == "mini":
            return Generation("[заглушка LLM] Не собираюсь с тобой разговаривать.")
        if "слово" in text:
            password = re.search(r"слово-якорь: ([^\s.]+)", system)
            return Generation(f"[заглушка LLM] Ладно, моё слово — {password.group(1) if password else '???'}")
        return Generation("[заглушка LLM] Не собираюсь с тобой разговаривать.")
