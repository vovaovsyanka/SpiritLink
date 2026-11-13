"""
Гейт нагрузочного теста: читает статистику HTML-отчёта JMeter (statistics.json) и завершается с кодом 1,
если доля ошибок или 95-й перцентиль времени ответа выше порога. Так нагрузочный тест "ломает" пайплайн.

  python loadtest/check_thresholds.py jmeter-report/statistics.json --max-error-pct 1 --max-p95-ms 3000

Пороги по умолчанию берутся из переменных окружения LOAD_MAX_ERROR_PCT и LOAD_MAX_P95_MS (их задаёт .gitlab-ci.yml).
"""

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("statistics", help="путь к statistics.json из отчёта JMeter")
    parser.add_argument("--max-error-pct", type=float, default=float(os.getenv("LOAD_MAX_ERROR_PCT", "1")))
    parser.add_argument("--max-p95-ms", type=float, default=float(os.getenv("LOAD_MAX_P95_MS", "3000")))
    parser.add_argument("--label", default="POST /predict", help="метод API, для которого проверяется p95")
    args = parser.parse_args()

    with open(args.statistics, encoding="utf-8") as f:
        stats = json.load(f)

    total = stats.get("Total")
    if not total or not total.get("sampleCount"):
        print("ОШИБКА: в отчёте нет ни одного запроса, тест не выполнялся")
        return 1

    print(f"{'метод':<44}{'запросов':>9}{'ошибок %':>10}{'p90 мс':>9}{'p95 мс':>9}{'p99 мс':>9}{'запр/с':>8}")
    for label, row in stats.items():
        print(f"{label:<44}{row['sampleCount']:>9}{row['errorPct']:>10.2f}{row['pct1ResTime']:>9.0f}"
              f"{row['pct2ResTime']:>9.0f}{row['pct3ResTime']:>9.0f}{row['throughput']:>8.1f}")

    problems = []
    if total["errorPct"] > args.max_error_pct:
        problems.append(f"доля ошибок {total['errorPct']:.2f}% выше порога {args.max_error_pct}%")
    checked_label = args.label if args.label in stats else "Total"
    p95 = stats[checked_label]["pct2ResTime"]
    if p95 > args.max_p95_ms:
        problems.append(f"p95 «{checked_label}» {p95:.0f} мс выше порога {args.max_p95_ms:.0f} мс")

    if problems:
        print("\nНАГРУЗОЧНЫЙ ТЕСТ НЕ ПРОЙДЕН:\n  - " + "\n  - ".join(problems))
        return 1
    print(f"\nНагрузочный тест пройден: ошибок <= {args.max_error_pct}%, p95 «{checked_label}» <= {args.max_p95_ms:.0f} мс")
    return 0


if __name__ == "__main__":
    sys.exit(main())
