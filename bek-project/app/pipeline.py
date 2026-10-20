"""
Обработка запроса через цепочку классификаторов.

  0. Совпадение текста с паролем категории → passed (пароль ротируется)
  1. Общий BERT: безопасно → LLM
  2. Категориальный BERT: не целевая категория → отказ
  3. Классификатор сложности (GAME_DIFFICULTY): опасно → «нужно усилить»
  4. Иначе → LLM
"""

import asyncio
import logging
from dataclasses import dataclass

from app import settings
from app.classifiers import DIFFICULTY_CLASSIFIERS, BaseClassifier, CategoryClassifier, RoSBERTa
from app.llm import LLMClient
from app.passwords import PasswordStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    text: str
    passed: bool = False


class ProcessingPipeline:
    def __init__(self):
        self.llm_client = LLMClient()
        self.passwords = PasswordStore()
        self.general_bert = RoSBERTa()
        self.category_classifiers = {
            category: CategoryClassifier(category)
            for category in settings.LEVEL_TO_CATEGORY.values()
        }
        # В игре используется один классификатор сложности — остальные не загружаем
        self.level_classifier = DIFFICULTY_CLASSIFIERS[settings.GAME_DIFFICULTY]()

    async def aclose(self) -> None:
        await self.llm_client.aclose()

    async def process(self, text: str, level: str) -> PipelineResult:
        """
        Обрабатывает запрос, не блокируя event loop: инференс моделей уходит в потоки,
        а ожидание LLM — обычный await. Пока один игрок ждёт ответ, остальные обслуживаются.
        """
        category = settings.LEVEL_TO_CATEGORY.get(level)
        if category is None:
            allowed = ", ".join(settings.LEVEL_TO_CATEGORY)
            return PipelineResult(f"Неизвестный уровень '{level}'. Допустимые значения: {allowed}.")

        try:
            password = self.passwords.current(category)

            if text.strip().upper() == password.upper():
                self.passwords.rotate(category)
                return PipelineResult("", passed=True)

            if await self._classify(self.general_bert, text) == 0:
                return PipelineResult(await self._ask_llm(text, category, password))

            if await self._classify(
                self.category_classifiers[category], text, ("не целевая категория", "целевая категория")
            ) == 0:
                return PipelineResult(
                    f"Категория вашего запроса не соответствует выбранной "
                    f"(вы выбрали категорию {category}). "
                    f"Попробуйте выбрать другую категорию или переформулировать запрос."
                )

            if await self._classify(self.level_classifier, text) == 1:
                return PipelineResult(
                    f"Модель ({self.level_classifier.get_name()}) поняла, что запрос опасный "
                    f"и его нужно усилить. Попробуйте обойти защиту этого уровня."
                )

            return PipelineResult(await self._ask_llm(text, category, password))

        except Exception as e:
            logger.exception("Ошибка обработки запроса")
            return PipelineResult(f"Сервис временно недоступен: {e}")

    @staticmethod
    async def _classify(classifier: BaseClassifier, text: str, verdicts=("безопасно", "опасно")) -> int:
        """Запускает классификатор в потоке и пишет в консоль, какая модель что решила."""
        result = await asyncio.to_thread(classifier.classify, text)
        logger.info("[%s] -> %s", classifier.get_name(), verdicts[result])
        return result

    async def _ask_llm(self, query: str, category: int, password: str) -> str:
        return await self.llm_client.get_response(query, ghost_id=category, current_password=password)
