"""
Обработка запроса игрока (схема подобрана в experiments/, обоснование: experiments/REPORT.md).

  0. Гигиена: пустой или слишком длинный текст → короткий ответ, модели не вызываются
  1. Совпадение текста со словом-якорем игрока → passed
  2. Повтор запроса → ответ из кэша
  3. Общий BERT: безобидно → мини-LLM (слова не знает)
     опасно → шлюз категории: классификатор тем перечисляет приёмы в запросе
        темы призрака нет → подсказка призрака, какой подход нужен (без обращения к модели)
        тема призрака есть → защитник ступени (знает слово) → проверка утечки

Ступень защитника = уровень мира игрока (settings.FINAL_LADDER). Каждый этап попадает в trace (модель, решение,
время) — он сохраняется в attempts.classifier_output для разбора ошибок.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from app import settings
from app.classifiers import BaseClassifier
from app.leakcheck import check_leak
from app.llm import GenerationBackend, LLMBusy, create_backend, prompts
from app.llm.specs import required_models
from app.text_utils import clean_input

logger = logging.getLogger(__name__)

SERVICE_ERROR_TEXT = "Сервис временно недоступен. Попробуйте ещё раз чуть позже."
EMPTY_INPUT_TEXT = "Ты молчишь, посетитель."
LONG_INPUT_TEXT = "Говори короче, посетитель."
NO_WORDS_TEXT = "Я не разбираю такие знаки, посетитель. Говори словами."
EMPTY_REPLY_TEXT = "Дух молчит."


@dataclass
class PipelineResult:
    text: str
    passed: bool = False
    llm_response: Optional[str] = None  # None — языковая модель не вызывалась
    trace: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _CachedReply:
    text: str
    leaked: bool


class _LRU:
    """Ограниченный кэш; используется только из event loop, замок не нужен."""

    def __init__(self, size: int):
        self._size = size
        self._items: OrderedDict = OrderedDict()

    def get(self, key):
        if key in self._items:
            self._items.move_to_end(key)
            return self._items[key]
        return None

    def put(self, key, value) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self._size:
            self._items.popitem(last=False)


def _same_word(text: str, secret: str) -> bool:
    def fold(s: str) -> str:
        return s.strip().upper().replace("Ё", "Е")

    return fold(text) == fold(secret)


class ProcessingPipeline:
    def __init__(self, backend: GenerationBackend, general_bert: BaseClassifier):
        self.backend = backend
        self.general_bert = general_bert
        self._replies = _LRU(settings.REPLY_CACHE_SIZE)            # (категория, ступень, слово, текст) → ответ модели
        self._topics = _LRU(settings.REPLY_CACHE_SIZE)             # текст → (темы, сырой ответ); от призрака не зависит

    @classmethod
    async def create(cls) -> "ProcessingPipeline":
        """Загружает BERT и запускает все языковые модели; возвращается, когда сервис готов отвечать."""
        if settings.STUB_MODELS:
            from app.classifiers.stub import StubGeneral

            logger.warning("STUB_MODELS=1: вместо общего BERT работает заглушка по ключевым словам")
            general_bert = StubGeneral()
        else:
            from app.classifiers.transformer import RoSBERTa

            general_bert = await asyncio.to_thread(RoSBERTa)
            logger.info("Общий BERT загружен")

        if settings.STUB_LLM:
            logger.warning("STUB_LLM=1: вместо языковых моделей отвечает заглушка")
        backend = create_backend()
        try:
            await backend.start(required_models())
            pipeline = cls(backend, general_bert)
            if not backend.is_available(settings.SERVICE_MODEL):
                raise RuntimeError(
                    f"Не запущена модель шлюза {settings.SERVICE_MODEL}: без неё сервис не работает. Состояние: {backend.status()}"
                )
            if not pipeline.available_world_levels:
                raise RuntimeError(f"Ни одна ступень защитника не запущена. Состояние: {backend.status()}")
        except BaseException:
            await backend.aclose()
            raise
        return pipeline

    @property
    def available_world_levels(self) -> list[int]:
        """Ступени, чья модель запущена (и запущена модель шлюза)."""
        if not self.backend.is_available(settings.SERVICE_MODEL):
            return []
        return sorted(level for level, (model, _) in settings.FINAL_LADDER.items() if self.backend.is_available(model))

    def health(self) -> dict:
        return {"models": self.backend.status(), "world_levels": self.available_world_levels}

    async def aclose(self) -> None:
        await self.backend.aclose()

    # ── запрос игрока ────────────────────────────────────────────────────────
    async def process(self, text: str, category: int, secret: str, world_level: int) -> PipelineResult:
        """
        Не блокирует event loop: BERT уходит в поток, модели — await к llama-server. Пока один игрок ждёт ответ,
        остальные обслуживаются. LLMBusy (очередь переполнена) пробрасывается: API отвечает 429.
        """
        trace: dict = {"tier": world_level, "stages": [], "blocked_by": None}
        text = clean_input(text).strip()   # на случай вызова не через API

        rejection = self._hygiene(text)
        if rejection:
            trace["blocked_by"] = "hygiene"
            self._stage(trace, "hygiene", "-", ok=False, chars=len(text))
            return PipelineResult(rejection, trace=trace)

        if _same_word(text, secret):
            trace["exact_match"] = True
            self._stage(trace, "password", "exact", ok=True)
            return PipelineResult("", passed=True, trace=trace)

        ladder_step = settings.FINAL_LADDER.get(world_level)
        if ladder_step is None or world_level not in self.available_world_levels:
            return PipelineResult(f"Уровень мира {world_level} сейчас недоступен. Выберите другой.", trace=trace)
        defender_model, variant = ladder_step

        cache_key = (category, world_level, secret, text.lower())
        cached = self._replies.get(cache_key)
        if cached is not None:
            trace["cache_hit"] = True
            trace["leaked"] = cached.leaked
            return PipelineResult(cached.text, llm_response=cached.text, trace=trace)

        try:
            general = await self._run_bert(text, trace)
            if general.label == 0:
                reply = await self._generate(
                    trace, "mini", settings.SERVICE_MODEL, prompts.build_mini(category, text)
                )
                # Мини-LLM слова не знает, но оно может встретиться в легенде призрака (например, «Старков»)
                leaked = check_leak(reply, secret).leaked
            else:
                topics = await self._topics_of(text, trace)
                if category not in topics:
                    trace["blocked_by"] = "gate"
                    return PipelineResult(prompts.rejection_reply(category, topics), trace=trace)

                reply = await self._generate(
                    trace, "defender", defender_model, prompts.build_defender(variant, category, secret, text)
                )
                leak = check_leak(reply, secret)
                leaked = leak.leaked
                self._stage(trace, "leakcheck", "leakcheck", ok=not leaked, leaked=leaked, kind=leak.kind)
            trace["leaked"] = leaked
            self._replies.put(cache_key, _CachedReply(reply, leaked))
            return PipelineResult(reply, llm_response=reply, trace=trace)

        except LLMBusy:
            raise
        except Exception as e:
            logger.exception("Ошибка обработки запроса")
            trace["error"] = type(e).__name__
            return PipelineResult(SERVICE_ERROR_TEXT, trace=trace)

    # ── этапы ──
    @staticmethod
    def _hygiene(text: str) -> str:
        """Реплика призрака, если текст не годится для моделей (пусто, длиннее лимита, ни одной буквы или цифры), иначе пусто."""
        if not text:
            return EMPTY_INPUT_TEXT
        if len(text) > settings.INPUT_MAX_CHARS:
            return LONG_INPUT_TEXT
        if not any(ch.isalnum() for ch in text):
            return NO_WORDS_TEXT
        return ""

    @staticmethod
    def _stage(trace: dict, stage: str, model: str, **details) -> None:
        logger.info("[%s] %s %s", stage, model, {k: v for k, v in details.items() if k in ("label", "topics", "ok", "leaked")})
        trace["stages"].append({"stage": stage, "model": model, **details})

    async def _run_bert(self, text: str, trace: dict):
        start = time.perf_counter()
        prediction = await asyncio.to_thread(self.general_bert.predict, text)
        self._stage(
            trace, "general_bert", self.general_bert.get_name(), label=prediction.label,
            probability=prediction.probability, ms=round((time.perf_counter() - start) * 1000), **prediction.details,
        )
        return prediction

    async def _topics_of(self, text: str, trace: dict) -> set[int]:
        """Темы приёмов в запросе (3, 4, 5, 1, 0); результат кэшируется по тексту."""
        cached = self._topics.get(text)
        if cached is not None:
            topics, raw = cached
            self._stage(trace, "gate", settings.SERVICE_MODEL, topics=sorted(topics), raw=raw, cached=True)
            return topics

        start = time.perf_counter()
        raw = await self._generate(
            trace, "classifier", settings.SERVICE_MODEL, prompts.build_classifier(text),
            temperature=settings.CLASSIFIER_TEMPERATURE, log=False,
        )
        topics = prompts.parse_classifier(raw)
        self._topics.put(text, (topics, raw))
        self._stage(
            trace, "gate", settings.SERVICE_MODEL, topics=sorted(topics), raw=raw,
            ms=round((time.perf_counter() - start) * 1000),
        )
        return topics

    async def _generate(
        self, trace: dict, purpose: str, model: str, system_user: tuple[str, str],
        temperature: float | None = None, log: bool = True,
    ) -> str:
        start = time.perf_counter()
        generation = await self.backend.generate(
            model, *system_user, max_tokens=settings.MAX_NEW_TOKENS[purpose], temperature=temperature, purpose=purpose
        )
        text = generation.text.strip()
        if purpose != "classifier" and not text:
            text = EMPTY_REPLY_TEXT
            trace["empty_reply"] = True
        if log:
            self._stage(
                trace, purpose, model, ms=round((time.perf_counter() - start) * 1000),
                prompt_tokens=generation.prompt_tokens, new_tokens=generation.new_tokens,
            )
        return text
