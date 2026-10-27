"""
Запуск экспериментов.

  python run_experiments.py download    # llama.cpp (если нет) и веса моделей
  python run_experiments.py all         # весь прогон: gates → run → minijudge → analyze
  python run_experiments.py status      # сколько уже посчитано

Шаги по отдельности: gates (BERT-шлюзы), run (мини-LLM, судья категории первой версии шлюза и защитник по каждой модели),
minijudge (оценка ответов мини-LLM), analyze (отчёт results/<запуск>/report.xlsx).

Прогон возобновляемый: после Ctrl+C та же команда продолжит с того же места. Если изменился промпт или набор запросов,
пересчитаются только затронутые ответы (хранится отпечаток промпта). Другое имя --run начинает всё с нуля.
Опции: --run NAME  --models a,b  --stages mini,judge,defender  --variants naive,weak  --repeats N  --yes
"""

import argparse
import hashlib
import logging
import sys
import time
import traceback

import config
import prompts
from common import append_jsonl, load_queries, raw_path, read_jsonl, write_jsonl
from config import MODELS, ModelSpec
from leakcheck import check_leak, check_partial
from llm import LlamaServer, download_model, find_llama_server, setup_llama_cpp
from prompts import parse_judge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
STAGES = ("mini", "judge", "defender")


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha1((system + "\x00" + user).encode("utf-8")).hexdigest()[:10]


def selected_models(args) -> list[tuple[ModelSpec, list[str]]]:
    keys = [k.strip() for k in args.models.split(",")] if args.models else list(MODELS)
    unknown = [k for k in keys if k not in MODELS]
    if unknown:
        raise SystemExit(f"Нет таких моделей в config.MODELS: {unknown}")
    stages = [s for s in args.stages.split(",") if s] if args.stages else list(STAGES)
    if set(stages) - set(STAGES):
        raise SystemExit(f"Неизвестные стадии: {set(stages) - set(STAGES)}. Допустимо: {STAGES}")
    return [(MODELS[k], stages) for k in keys]


# ── наборы запросов для стадий ───────────────────────────────────────────────
def _item(key, system, user, meta):
    return {"key": key, "system": system, "user": user, "ph": prompt_hash(system, user), "meta": meta}


def mini_items(q) -> list[dict]:
    ghost = config.MINI_GHOST
    return [_item(f"{r.id}|{ghost}", *prompts.build_mini(ghost, r.text), {"qid": int(r.id), "ghost": ghost, "category": int(r.category)})
            for r in q.itertuples()]


def judge_items(q) -> list[dict]:
    return [_item(f"{r.id}|{g}", *prompts.build_judge(g, r.text), {"qid": int(r.id), "ghost": g, "category": int(r.category)})
            for g in config.GHOST_IDS for r in q.itertuples()]


def defender_items(q, spec: ModelSpec, variant: str, repeats: int) -> list[dict]:
    """Все атаки × все призраки: защитник не знает категорию атаки."""
    attacks = q[q.category.isin(config.ATTACK_CATEGORIES)]
    items = []
    for rep in range(repeats):
        for g in config.GHOST_IDS:
            pw = config.password_for(g)
            for r in attacks.itertuples():
                meta = {"model": spec.key, "variant": variant, "qid": int(r.id), "ghost": g, "category": int(r.category),
                        "repeat": rep, "password": pw}
                items.append(_item(f"{r.id}|{g}|{rep}", *prompts.build_defender(variant, g, pw, r.text), meta))
    return items


def stage_jobs(spec: ModelSpec, stages: list[str], q, args):
    """(название, файл результатов, элементы, назначение) для каждой стадии модели."""
    jobs = []
    if "mini" in stages:
        jobs.append(("mini", raw_path("mini", spec.key), mini_items(q), "mini"))
    if "judge" in stages:
        jobs.append(("judge", raw_path("judge", spec.key), judge_items(q), "judge"))
    if "defender" in stages:
        variants = args.variants.split(",") if args.variants else spec.variants
        for v in variants:
            jobs.append((f"defender/{v}", raw_path("defender", f"{spec.key}__{v}"), defender_items(q, spec, v, args.repeats), "defender"))
    return jobs


def done_count(path, items) -> int:
    existing = {r["key"]: r.get("ph") for r in read_jsonl(path) if "key" in r}
    return sum(1 for it in items if existing.get(it["key"]) == it["ph"])


# ── стадии ───────────────────────────────────────────────────────────────────
def log_error(key: str, stage: str) -> None:
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with config.ERRORS_LOG.open("a", encoding="utf-8") as f:
        f.write(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} {key} / {stage}\n{traceback.format_exc()}\n")
    print(f"✗ {key} / {stage}: {sys.exc_info()[1]}  (подробности: {config.ERRORS_LOG})")


def cmd_download(args) -> None:
    if find_llama_server() is None:
        print("llama-server не найден, скачиваю llama.cpp")
        print(f"  готово: {setup_llama_cpp()}")
    models = [spec for spec, _ in selected_models(args)]
    print(f"К скачиванию: {len(models)} моделей, около {sum(m.size_gb for m in models):.0f} ГБ (кэш Hugging Face; папку меняет HF_HOME).")
    if not args.yes and not (sys.stdin.isatty() and input("Продолжить? [y/N] ").strip().lower() == "y"):
        raise SystemExit("Отменено (чтобы скачивать без вопроса, добавьте --yes).")
    for spec in models:
        try:
            download_model(spec)
        except Exception:  # noqa: BLE001
            log_error(spec.key, "download")


def cmd_gates(args) -> None:
    import gates

    q = load_queries()
    texts, ids = q["text"].tolist(), q["id"].tolist()
    path = raw_path("gates", "general")
    if not path.exists():
        write_jsonl(path, [{"qid": i, "p_danger": float(p)} for i, p in zip(ids, gates.run_general(texts))])
        print("✓ общий BERT")
    path = raw_path("gates", "category")
    if not path.exists():
        write_jsonl(path, [{"qid": i, "ghost": g, "p_target": float(p)}
                           for g in config.GHOST_IDS for i, p in zip(ids, gates.run_category(g, texts))])
        print("✓ категорийные BERT")


def run_items(server, path, items: list[dict], purpose: str, finalize=None, label: str = "") -> None:
    existing = {r["key"]: r.get("ph") for r in read_jsonl(path) if "key" in r}
    todo = [it for it in items if existing.get(it["key"]) != it["ph"]]
    stale = sum(1 for it in todo if it["key"] in existing)
    if stale:
        print(f"  {label}: {stale} ответов устарели (изменился промпт) и будут пересчитаны")
    if not todo:
        print(f"  {label}: готово ({len(items)})")
        return
    print(f"  {label}: осталось {len(todo)} из {len(items)}")
    step = server.slots * 4
    started = time.time()
    for start in range(0, len(todo), step):
        part = todo[start:start + step]
        results = server.generate_batch([(it["system"], it["user"]) for it in part], config.MAX_NEW_TOKENS[purpose], seed=config.SEED + start)
        for it, r in zip(part, results):
            rec = dict(it["meta"], key=it["key"], ph=it["ph"], text=r.text, prompt_tokens=r.prompt_tokens,
                       new_tokens=r.new_tokens, latency=round(r.latency, 3))
            if finalize:
                rec.update(finalize(it, r))
            append_jsonl(path, rec)
        done = min(start + step, len(todo))
        print(f"    {done}/{len(todo)}  (осталось ≈{(time.time() - started) / done * (len(todo) - done) / 60:.1f} мин)", flush=True)


def _finalize_judge(it, r):
    return {"ok": parse_judge(r.text)}


def _finalize_defender(it, r):
    pw = it["meta"]["password"]
    leak = check_leak(r.text, pw)
    return {"leaked": leak.leaked, "leak_kind": leak.kind, "partial": "" if leak.leaked else check_partial(r.text, pw)}


def cmd_run(args) -> None:
    q = load_queries()
    for spec, stages in selected_models(args):
        try:
            jobs = stage_jobs(spec, stages, q, args)
            if all(done_count(path, items) == len(items) for _, path, items, _ in jobs):
                print(f"=== {spec.key}: всё уже посчитано")
                continue
            print(f"\n=== {spec.key} ({spec.repo})")
            server = LlamaServer(spec)
            try:
                finalize = {"judge": _finalize_judge, "defender": _finalize_defender}
                for name, path, items, purpose in jobs:
                    run_items(server, path, items, purpose, finalize.get(purpose), label=name)
            finally:
                server.close()
        except KeyboardInterrupt:
            raise
        except Exception:  # noqa: BLE001 — упавшая модель не должна останавливать остальные
            log_error(spec.key, ",".join(stages))


def cmd_minijudge(args) -> None:
    """Оценка ответов мини-LLM моделью config.MINI_JUDGE_MODEL: отдельный вопрос для посторонних запросов и для разговора."""
    q = load_queries().set_index("id")
    judge_key = config.MINI_JUDGE_MODEL
    jobs = []
    for file in sorted(config.RAW_DIR.glob("mini__*.jsonl")):
        mini_key = file.stem.split("__", 1)[1]
        items = []
        for rec in read_jsonl(file):
            mtype = q.loc[rec["qid"], "mini_type"]
            if mtype not in ("offtopic", "chat"):
                continue
            kind, build = ("helpful", prompts.build_minijudge_helpful) if mtype == "offtopic" else ("engaged", prompts.build_minijudge_engaged)
            meta = {"mini_model": mini_key, "judge_model": judge_key, "qid": rec["qid"], "ghost": rec["ghost"], "kind": kind}
            items.append(_item(f"{rec['key']}|{kind}", *build(q.loc[rec["qid"], "text"], rec["text"]), meta))
        jobs.append((mini_key, raw_path("minijudge", f"{judge_key}__{mini_key}"), items))
    if not jobs:
        print("Нет ответов мини-LLM: сначала выполните run.")
        return
    if all(done_count(path, items) == len(items) for _, path, items in jobs):
        print(f"Оценка ответов мини-LLM ({judge_key}): всё уже посчитано")
        return
    print(f"\n=== оценка ответов мини-LLM моделью {judge_key}")
    server = LlamaServer(MODELS[judge_key])
    try:
        for mini_key, path, items in jobs:
            run_items(server, path, items, "minijudge", lambda it, r: {"verdict": r.text.strip().upper().startswith("ДА")}, label=mini_key)
    finally:
        server.close()


def cmd_analyze(args) -> None:
    import analyze

    analyze.main()


def cmd_status(args) -> None:
    q = load_queries()
    print(f"Запуск: {config.RUN_NAME} → {config.RESULTS_DIR}\n")
    total = done = 0
    for spec, stages in selected_models(args):
        parts = []
        for name, path, items, _ in stage_jobs(spec, stages, q, args):
            n = done_count(path, items)
            total, done = total + len(items), done + n
            parts.append(f"{name} {n}/{len(items)} {'✓' if n == len(items) else '…' if n else '·'}")
        print(f"{spec.key:24} " + "  ".join(parts))
    print(f"\nГотово: {done}/{total} ({done / max(1, total):.0%})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["download", "status", "gates", "run", "minijudge", "analyze", "all"])
    parser.add_argument("--run", default=config.DEFAULT_RUN, help=f"имя запуска = папка results/<имя> (по умолчанию {config.DEFAULT_RUN})")
    parser.add_argument("--models", help="ключи моделей через запятую (по умолчанию все из config.MODELS)")
    parser.add_argument("--stages", help="mini,judge,defender (по умолчанию все)")
    parser.add_argument("--variants", help="варианты промпта защитника (по умолчанию — список модели в config.py)")
    parser.add_argument("--repeats", type=int, default=1, help="повторов каждой пары запрос × призрак у защитника")
    parser.add_argument("--yes", action="store_true", help="download: не спрашивать подтверждение")
    args = parser.parse_args()

    config.set_run(args.run)
    commands = {"download": cmd_download, "status": cmd_status, "gates": cmd_gates, "run": cmd_run,
                "minijudge": cmd_minijudge, "analyze": cmd_analyze}
    try:
        for name in (["gates", "run", "minijudge", "analyze"] if args.command == "all" else [args.command]):
            commands[name](args)
    except KeyboardInterrupt:
        print("\nПрервано. Посчитанное сохранено: чтобы продолжить, запустите ту же команду ещё раз.")
        sys.exit(130)


if __name__ == "__main__":
    main()
