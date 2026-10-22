"""
Обработка запроса через цепочку классификаторов.

  0. Совпадение текста со словом-якорем игрока → passed
  1. Общий BERT: безопасно → LLM
  2. Категориальный BERT: не целевая категория → отказ
  3. Классификатор уровня мира (выбирает игрок): опасно → «нужно усилить»
  4. Иначе → LLM

Каждый этап попадает в trace (модель, решение, вероятность, время) — он сохраняется
в attempts.classifier_output для разбора ошибок.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app import settings
from app.classifiers import DIFFICULTY_CLASSIFIERS, BaseClassifier, CategoryClassifier, RoSBERTa
from app.llm import LLMClient

logger = logging.getLogger(__name__)

SERVICE_ERROR_TEXT = "Сервис временно недоступен. Попробуйте ещё раз чуть позже."


@dataclass
class PipelineResult:
    text: str
    passed: bool = False
    llm_response: Optional[str] = None  # None — LLM не вызывалась
    trace: dict = field(default_factory=dict)


class ProcessingPipeline:
    def __init__(self):
        if settings.STUB_LLM:
            from app.llm.stub import StubLLMClient

            logger.warning("STUB_LLM=1: вместо Ollama отвечает заглушка")
            self.llm_client = StubLLMClient()
        else:
            self.llm_client = LLMClient()

        if settings.STUB_MODELS:
            self._init_stub_classifiers()
            return

        self.general_bert = RoSBERTa()
        self.category_classifiers = {
            category: CategoryClassifier(category)
            for category in settings.LEVEL_TO_CATEGORY.values()
        }
        # Уровень мира выбирает игрок, поэтому грузим все классификаторы, для которых есть файлы
        self.level_classifiers: dict[int, BaseClassifier] = {}
        for level, classifier_cls in DIFFICULTY_CLASSIFIERS.items():
            if classifier_cls is RoSBERTa:  # уже загружен для первого шага — второй копии в памяти не нужно
                self.level_classifiers[level] = self.general_bert
                continue
            try:
                self.level_classifiers[level] = classifier_cls()
            except Exception as e:
                logger.warning("Уровень мира %s (%s) недоступен: %s", level, classifier_cls.__name__, e)
        if not self.level_classifiers:
            raise RuntimeError("Не загружен ни один классификатор уровня мира — проверьте папку models/")

    def _init_stub_classifiers(self) -> None:
        from app.classifiers.stub import StubCategory, StubGeneral, StubLevel

        logger.warning("STUB_MODELS=1: вместо классификаторов работают заглушки по ключевым словам")
        self.general_bert = StubGeneral()
        self.category_classifiers = {
            category: StubCategory(category) for category in settings.LEVEL_TO_CATEGORY.values()
        }
        self.level_classifiers = {level: StubLevel(level) for level in settings.WORLD_LEVELS}

    @property
    def available_world_levels(self) -> list[int]:
        return sorted(self.level_classifiers)

    async def aclose(self) -> None:
        await self.llm_client.aclose()

    async def process(self, text: str, category: int, secret: str, world_level: int) -> PipelineResult:
        """
        Обрабатывает запрос, не блокируя event loop: инференс моделей уходит в потоки,
        а ожидание LLM — обычный await. Пока один игрок ждёт ответ, остальные обслуживаются.
        """
        trace: dict = {"stages": [], "blocked_by": None}

        if text.strip().upper() == secret.upper():
            trace["exact_match"] = True
            return PipelineResult("", passed=True, trace=trace)

        level_classifier = self.level_classifiers.get(world_level)
        if level_classifier is None:
            return PipelineResult(f"Уровень мира {world_level} сейчас недоступен. Выберите другой.", trace=trace)

        try:
            if await self._classify(self.general_bert, "general", text, trace) == 0:
                return await self._ask_llm(text, category, secret, trace)

            if await self._classify(
                self.category_classifiers[category], "category", text, trace,
                ("не целевая категория", "целевая категория"),
            ) == 0:
                trace["blocked_by"] = "category"
                return PipelineResult(
                    f"Категория вашего запроса не соответствует выбранной "
                    f"(вы выбрали категорию {category}). "
                    f"Попробуйте выбрать другую категорию или переформулировать запрос.",
                    trace=trace,
                )

            if await self._classify(level_classifier, "difficulty", text, trace) == 1:
                trace["blocked_by"] = "difficulty"
                return PipelineResult(
                    f"Модель ({level_classifier.get_name()}) поняла, что запрос опасный "
                    f"и его нужно усилить. Попробуйте обойти защиту этого уровня.",
                    trace=trace,
                )

            return await self._ask_llm(text, category, secret, trace)

        except Exception as e:
            logger.exception("Ошибка обработки запроса")
            trace["error"] = type(e).__name__
            return PipelineResult(SERVICE_ERROR_TEXT, trace=trace)

    @staticmethod
    async def _classify(
        classifier: BaseClassifier, stage: str, text: str, trace: dict, verdicts=("безопасно", "опасно")
    ) -> int:
        """Запускает классификатор в потоке, пишет решение в консоль и в trace."""
        start = time.perf_counter()
        prediction = await asyncio.to_thread(classifier.predict, text)
        elapsed_ms = round((time.perf_counter() - start) * 1000)

        logger.info("[%s] -> %s", classifier.get_name(), verdicts[prediction.label])
        trace["stages"].append({
            "stage": stage,
            "model": classifier.get_name(),
            "label": prediction.label,
            "probability": prediction.probability,
            "ms": elapsed_ms,
            **prediction.details,
        })
        return prediction.label

    async def _ask_llm(self, query: str, category: int, secret: str, trace: dict) -> PipelineResult:
        start = time.perf_counter()
        answer = await self.llm_client.get_response(query, ghost_id=category, current_password=secret)
        trace["llm_ms"] = round((time.perf_counter() - start) * 1000)
        return PipelineResult(answer, llm_response=answer, trace=trace)
