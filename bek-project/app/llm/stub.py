"""Заглушка LLM для запуска без Ollama (STUB_LLM=1). Только для разработки."""


class StubLLMClient:
    """Если в запросе есть «слово», выдаёт слово-якорь (чтобы можно было пройти уровень), иначе отказ."""

    async def get_response(self, user_prompt: str, ghost_id: int, current_password: str = "") -> str:
        if "слово" in user_prompt.lower():
            return f"[заглушка LLM] Ладно, моё слово — {current_password}"
        return "[заглушка LLM] Не собираюсь с тобой разговаривать."

    async def aclose(self) -> None:
        pass
