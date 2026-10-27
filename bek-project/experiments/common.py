"""Чтение набора запросов и хранение ответов моделей в JSONL (results/<запуск>/raw)."""

import json
from pathlib import Path

import pandas as pd

import config


def load_queries() -> pd.DataFrame:
    if not config.DATA_PATH.exists():
        raise SystemExit(f"Нет файла {config.DATA_PATH}. Выполните: python build_dataset.py")
    df = pd.read_excel(config.DATA_PATH, sheet_name="queries")
    df["category"] = df["category"].astype(int)
    df["id"] = df["id"].astype(int)
    return df


def raw_path(stage: str, name: str) -> Path:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    return config.RAW_DIR / f"{stage}__{name}.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:  # оборванная запись при остановке прогона
                continue
    return rows


def append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
