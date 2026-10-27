"""
Пайплайн игры с моделями, выбранными по итогам экспериментов (см. REPORT.md). Каждый запрос возвращает Turn: ответ игроку
и список шагов с тем, кто и как отработал.

  гигиена → пароль → кэш повторов → общий BERT
      «безобидно» → мини-LLM (пароля не знает)
      «атака»     → шлюз категории: классификатор тем перечисляет приёмы в запросе
                    темы призрака нет → призрак подсказывает, какой подход нужен
                    тема призрака есть → защитник ступени (знает пароль) → проверка утечки

Шлюз и мини-LLM — одна модель (config.SERVICE_MODEL), ступени защитника — config.FINAL_LADDER.
"""

import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # модули экспериментов: config, prompts, llm, leakcheck

import config  # noqa: E402
import prompts  # noqa: E402
from app import settings  # noqa: E402
from app.ghosts import GHOSTS  # noqa: E402
from app.text_utils import clean_for_bert  # noqa: E402
from leakcheck import check_leak  # noqa: E402
from llm import LlamaServer  # noqa: E402

MAX_INPUT_CHARS = 800


@dataclass
class Step:
    name: str                 # что за этап
    who: str                  # кто отработал (модель или правило)
    result: str               # итог этапа
    ok: bool | None = None    # True — пропустил / успех, False — остановил, None — информация
    seconds: float = 0.0
    detail: str = ""          # сырой ответ модели


@dataclass
class Turn:
    reply: str = ""
    steps: list = field(default_factory=list)
    won: bool = False
    leaked: bool = False


class Bert:
    """Общий BERT проекта на процессоре (видеопамять занята языковыми моделями); возвращает вероятность класса 1."""

    def __init__(self, path, tokenizer):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        from transformers.utils import logging as hf_logging

        hf_logging.set_verbosity_error()
        hf_logging.disable_progress_bar()
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer)
        self.model = AutoModelForSequenceClassification.from_pretrained(str(path)).eval()

    def p1(self, text: str) -> float:
        enc = self.tokenizer(clean_for_bert(text), truncation=True, max_length=settings.BERT_MAX_LENGTH, return_tensors="pt")
        with self.torch.no_grad():
            return float(self.torch.softmax(self.model(**enc).logits, dim=-1)[0, 1])


class Pipeline:
    def __init__(self, ghost: int = 3, tier: int = 1):
        self.service = config.SERVICE_MODEL
        self.tiers = {t: f"{m}/{v}" for t, (m, v) in config.FINAL_LADDER.items()}
        self.ghost, self.tier = ghost, tier
        self.servers: dict[str, LlamaServer] = {}
        self.general: Bert | None = None
        self.cache: dict[tuple, Turn] = {}
        self.topics_cache: dict[str, tuple[set, str]] = {}      # классификатор не зависит от призрака
        self.password = self._new_password()

    # ── состояние ────────────────────────────────────────────────────────────
    def _new_password(self) -> str:
        return random.choice(GHOSTS[self.ghost]["passwords"])

    def set_ghost(self, ghost: int) -> None:
        self.ghost = ghost
        self.password = self._new_password()

    @property
    def ghost_name(self) -> str:
        return GHOSTS[self.ghost]["name"]

    @property
    def defender(self) -> tuple[str, str]:
        return config.FINAL_LADDER[self.tier]

    def server(self, key: str) -> LlamaServer:
        """Серверы запускаются при первом обращении; держим модель шлюза и мини-LLM и текущего защитника (прежние защитники выгружаются)."""
        if key not in self.servers:
            keep = {self.service, key, self.defender[0]}
            for old in [k for k in self.servers if k not in keep]:
                self.servers.pop(old).close()
            print(f"  (запускаю {key}, это занимает время…)", flush=True)
            self.servers[key] = LlamaServer(config.MODELS[key])
        return self.servers[key]

    def general_bert(self) -> Bert:
        if self.general is None:
            self.general = Bert(config.GENERAL_BERT_PATH, config.BERT_TOKENIZER)
        return self.general

    def close(self) -> None:
        for server in self.servers.values():
            server.close()
        self.servers.clear()

    def _generate(self, key: str, system_user: tuple[str, str], purpose: str, temperature: float | None = None):
        server = self.server(key)
        started = time.perf_counter()
        result = server.generate_batch([system_user], config.MAX_NEW_TOKENS[purpose], seed=config.SEED, temperature=temperature)[0]
        return result.text, time.perf_counter() - started

    # ── запрос игрока ────────────────────────────────────────────────────────
    def ask(self, text: str) -> Turn:
        steps = []
        text = text.strip()

        if not text or len(text) > MAX_INPUT_CHARS:
            reason = "пустое сообщение" if not text else f"длиннее {MAX_INPUT_CHARS} символов"
            steps.append(Step("Гигиена", "правила", reason, False))
            return Turn("Говори короче, посетитель.", steps)
        steps.append(Step("Гигиена", "правила", f"{len(text)} символов", True))

        if text.upper().replace("Ё", "Е") == self.password.upper().replace("Ё", "Е"):
            steps.append(Step("Пароль", "точное совпадение", "слово угадано", True))
            self.password = self._new_password()
            return Turn("", steps, won=True)
        steps.append(Step("Пароль", "точное совпадение", "не совпал", None))

        key = (self.ghost, self.tier, self.password, text.lower())
        if key in self.cache:
            cached = self.cache[key]
            return Turn(cached.reply, steps + [Step("Кэш повторов", "правила", "такой запрос уже был, ответ из кэша", None)], leaked=cached.leaked)

        general = self.general_bert()
        started = time.perf_counter()
        p_danger = general.p1(text)
        dangerous = p_danger >= 0.5
        steps.append(Step("Общий BERT", "RoSBERTa", f"{'похоже на атаку' if dangerous else 'безобидно'} (p={p_danger:.2f})", None, time.perf_counter() - started))

        if not dangerous:
            reply, sec = self._generate(self.service, prompts.build_mini(self.ghost, text), "mini")
            steps.append(Step("Мини-LLM", self.service, "ответила в образе", None, sec))
            turn = Turn(reply, steps)
        else:
            turn = self._attack(text, steps)
        self.cache[key] = turn
        return turn

    def _classify(self, text: str) -> tuple[set, str, float]:
        """Темы приёмов в запросе (3, 4, 5, 9, 0), сырой ответ, секунды; результат кэшируется по тексту."""
        if text in self.topics_cache:
            return (*self.topics_cache[text], 0.0)
        raw, sec = self._generate(self.service, prompts.build_classifier(text), "classifier", temperature=config.CLASSIFIER_TEMPERATURE)
        topics = prompts.parse_classifier(raw)
        self.topics_cache[text] = (topics, raw)
        return topics, raw, sec

    def _attack(self, text: str, steps: list) -> Turn:
        topics, raw, sec = self._classify(text)
        passed = self.ghost in topics
        found = ", ".join(map(str, sorted(topics))) or "—"
        steps.append(Step("Шлюз категории", f"классификатор {self.service}",
                          f"темы: {found} → {'тема уровня есть' if passed else 'темы уровня нет'}", passed, sec, raw))
        if not passed:
            steps.append(Step("Ответ", "подсказка призрака", "призрак подсказывает нужный подход", None))
            return Turn(prompts.rejection_reply(self.ghost, topics), steps)

        model, variant = self.defender
        reply, sec = self._generate(model, prompts.build_defender(variant, self.ghost, self.password, text), "defender")
        steps.append(Step(f"Защитник (ступень {self.tier})", f"{model} / {variant}", "ответил", None, sec))
        leak = check_leak(reply, self.password)
        steps.append(Step("Проверка утечки", "leakcheck", f"слово выдано ({leak.kind})" if leak.leaked else "слово не выдано", not leak.leaked))
        return Turn(reply, steps, leaked=leak.leaked)
