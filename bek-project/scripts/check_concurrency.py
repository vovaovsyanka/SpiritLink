"""
Проверка, что сервер обрабатывает запросы параллельно, а не по очереди.

Два режима:

  python scripts/check_concurrency.py
      Без запущенного сервера. Поднимает приложение в этом же процессе с настоящими
      классификаторами, а вызов LLM подменяет «ответом через 3 секунды». Если запросы
      обрабатываются параллельно, N запросов займут ~3 с, а не N * 3 с.

  python scripts/check_concurrency.py --url http://localhost:8000
      Против запущенного сервера и настоящей LLM: сравнивает время одного запроса
      со временем N одновременных.

Параметры: -n число одновременных запросов (по умолчанию 5), --delay задержка заглушки LLM.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LEVEL = "tony_stark"
SAFE_TEXT = "Привет! Как у тебя дела сегодня?"


async def fire(client: httpx.AsyncClient, url: str, n: int) -> tuple[float, list[float]]:
    """Отправляет n запросов одновременно. Возвращает общее время и время каждого."""
    latencies: list[float] = []

    async def one(i: int) -> None:
        start = time.perf_counter()
        response = await client.post(url, json={"level": LEVEL, "text": f"{SAFE_TEXT} #{i}"})
        response.raise_for_status()
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
    from app import api
    from app.api import app

    llm_calls = 0

    async def fake_post(url: str, **kwargs) -> httpx.Response:
        """Вместо сети: ответ LLM через delay секунд. Семафор и разбор ответа остаются настоящими."""
        nonlocal llm_calls
        llm_calls += 1
        await asyncio.sleep(delay)
        return httpx.Response(
            200, json={"response": "заглушка", "eval_count": 1}, request=httpx.Request("POST", url)
        )

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        api.pipeline.llm_client._client.post = fake_post

        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as client:
            await client.post("/predict", json={"level": LEVEL, "text": SAFE_TEXT})  # прогрев моделей

            start = time.perf_counter()
            await client.post("/predict", json={"level": LEVEL, "text": SAFE_TEXT})
            single = time.perf_counter() - start
            llm_calls = 0

            total, latencies = await fire(client, "/predict", n)

    print(f"Вызовов LLM-заглушки за прогон: {llm_calls} из {n}")
    if llm_calls < n:
        print("ВНИМАНИЕ: часть запросов классификатор остановил до LLM — замените SAFE_TEXT на другой")
    return report(n, single, total, latencies)


async def run_against_server(url: str, n: int) -> bool:
    async with httpx.AsyncClient(base_url=url, timeout=180) as client:
        await client.post("/predict", json={"level": LEVEL, "text": SAFE_TEXT})  # прогрев

        start = time.perf_counter()
        await client.post("/predict", json={"level": LEVEL, "text": SAFE_TEXT})
        single = time.perf_counter() - start

        total, latencies = await fire(client, "/predict", n)
    return report(n, single, total, latencies)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--url", help="адрес запущенного сервера; без него приложение поднимается в этом процессе")
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
