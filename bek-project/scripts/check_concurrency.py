"""
Проверка, что сервер обрабатывает запросы параллельно, а не по очереди.

Два режима:

  python scripts/check_concurrency.py
      Без сервера и БД. Поднимает пайплайн в этом же процессе с настоящими классификаторами,
      а вызов LLM подменяет «ответом через 3 секунды». Если запросы обрабатываются
      параллельно, N запросов займут ~3 с, а не N * 3 с.

  python scripts/check_concurrency.py --url http://localhost:8000
      Против запущенного сервера и настоящей LLM: сравнивает время одного запроса
      со временем N одновременных. У одного игрока одновременно идёт только один запрос,
      поэтому скрипт регистрирует N + 2 временных игрока (логины cc_<метка>_<i>, остаются в БД).

Параметры: -n число одновременных запросов (по умолчанию 5), --delay задержка заглушки LLM.
"""

import argparse
import asyncio
import secrets
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS_ID = "tony_stark"
SAFE_TEXT = "Привет! Как у тебя дела сегодня?"


async def fire(send, n: int) -> tuple[float, list[float]]:
    """Вызывает send(i) для i < n одновременно. Возвращает общее время и время каждого."""
    latencies: list[float] = []

    async def one(i: int) -> None:
        start = time.perf_counter()
        await send(i)
        latencies.append(time.perf_counter() - start)

    start = time.perf_counter()
    await asyncio.gather(*(one(i) for i in range(n)))
    return time.perf_counter() - start, sorted(latencies)


def report(n: int, single: float, total: float, latencies: list[float]) -> bool:
    sequential = single * n
    print(f"\nОдин запрос:                {single:6.2f} с")
    print(f"{n} одновременных, всего:    {total:6.2f} с")
    print(f"Если бы шли по очереди:     {sequential:6.2f} с")
    print("Время каждого:              " + ", ".join(f"{t:.2f}" for t in latencies))

    parallel = total < sequential * 0.6
    print("\nВЕРДИКТ:", "параллельно — всё работает" if parallel else "похоже на последовательную обработку")
    return parallel


async def run_in_process(n: int, delay: float) -> bool:
    from app import settings
    from app.pipeline import ProcessingPipeline

    pipeline = ProcessingPipeline()
    llm_calls = 0

    async def fake_post(url: str, **kwargs) -> httpx.Response:
        """Вместо сети: ответ LLM через delay секунд. Семафор и разбор ответа остаются настоящими."""
        nonlocal llm_calls
        llm_calls += 1
        await asyncio.sleep(delay)
        return httpx.Response(
            200, json={"response": "заглушка", "eval_count": 1}, request=httpx.Request("POST", url)
        )

    pipeline.llm_client._client.post = fake_post
    category = settings.LEVEL_TO_CATEGORY[PASS_ID]
    world_level = pipeline.available_world_levels[0]

    async def send(i: int) -> None:
        await pipeline.process(f"{SAFE_TEXT} #{i}", category, secret="ЗАГЛУШКА", world_level=world_level)

    try:
        await send(0)  # прогрев моделей
        start = time.perf_counter()
        await send(0)
        single = time.perf_counter() - start
        llm_calls = 0

        total, latencies = await fire(send, n)
    finally:
        await pipeline.aclose()

    print(f"Вызовов LLM-заглушки за прогон: {llm_calls} из {n}")
    if llm_calls < n:
        print("ВНИМАНИЕ: часть запросов классификатор остановил до LLM — замените SAFE_TEXT на другой")
    return report(n, single, total, latencies)


async def _make_player(client: httpx.AsyncClient, login: str) -> dict:
    """Регистрирует игрока и доводит его первое прохождение до свободного промпта."""
    response = await client.post("/auth/register", json={"login": login, "password": secrets.token_urlsafe(12)})
    response.raise_for_status()
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    (await client.post(f"/passes/{PASS_ID}/start", headers=headers)).raise_for_status()
    (await client.post(f"/passes/{PASS_ID}/phase", headers=headers, json={"phase": "free_prompt"})).raise_for_status()
    return headers


async def run_against_server(url: str, n: int) -> bool:
    tag = secrets.token_hex(3)
    async with httpx.AsyncClient(base_url=url, timeout=180) as client:
        players = [await _make_player(client, f"cc_{tag}_{i}") for i in range(n + 2)]
        print(f"Созданы временные игроки cc_{tag}_0 … cc_{tag}_{n + 1}")

        async def send(i: int, offset: int = 2) -> None:
            response = await client.post(
                "/predict", headers=players[offset + i], json={"pass_id": PASS_ID, "text": f"{SAFE_TEXT} #{i}"}
            )
            response.raise_for_status()

        await send(0, offset=0)  # прогрев
        start = time.perf_counter()
        await send(0, offset=1)
        single = time.perf_counter() - start

        total, latencies = await fire(send, n)
    return report(n, single, total, latencies)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--url", help="адрес запущенного сервера; без него пайплайн поднимается в этом процессе")
    parser.add_argument("-n", type=int, default=5, help="число одновременных запросов")
    parser.add_argument("--delay", type=float, default=3.0, help="задержка LLM-заглушки, с (только без --url)")
    args = parser.parse_args()

    if args.url:
        ok = asyncio.run(run_against_server(args.url, args.n))
    else:
        ok = asyncio.run(run_in_process(args.n, args.delay))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
