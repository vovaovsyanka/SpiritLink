from app import settings

from .backend import Generation, GenerationBackend, LLMBusy, LLMError


def create_backend() -> GenerationBackend:
    """Бэкенд по настройкам: STUB_LLM=1 — заглушка, иначе LLM_BACKEND."""
    if settings.STUB_LLM:
        from .stub import StubBackend

        return StubBackend()
    if settings.LLM_BACKEND == "llamacpp":
        from .llamacpp import LlamaCppBackend

        return LlamaCppBackend()
    raise ValueError(f"Неизвестный LLM_BACKEND={settings.LLM_BACKEND!r}. Поддерживается: llamacpp")


__all__ = ["Generation", "GenerationBackend", "LLMBusy", "LLMError", "create_backend"]
