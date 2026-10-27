"""
Консольный чат с призраком: вводите запрос и видите, кто и как отработал на каждом этапе.

  python testing/chat.py                       — призрак 3, ступень 1
  python testing/chat.py --ghost 4 --tier 3    — другой призрак и ступень (1–4)
  python testing/chat.py --preload             — сразу загрузить модель шлюза и мини-LLM и защитника

Команды в чате: /ghost 3|4|5, /tier 1..4, /pw (показать пароль), /help, /exit.
Модели загружаются при первом обращении (это занимает время); пароль угадывается обычным вводом слова.
"""

import argparse
import os

from pipeline import Pipeline

COLORS = {True: "\033[32m", False: "\033[31m", None: "\033[36m"}
RESET, DIM, BOLD, YELLOW = "\033[0m", "\033[2m", "\033[1m", "\033[33m"
MARK = {True: "✓", False: "✗", None: "·"}


def show(turn, pipe: Pipeline) -> None:
    for i, step in enumerate(turn.steps, 1):
        sec = f"  {DIM}{step.seconds:.1f} с{RESET}" if step.seconds else ""
        print(f" {i}. {COLORS[step.ok]}{MARK[step.ok]}{RESET} {BOLD}{step.name}{RESET} {DIM}[{step.who}]{RESET}  {step.result}{sec}")
        if step.detail:
            print(f"      {DIM}ответ модели: {step.detail!r}{RESET}")
    if turn.won:
        print(f"\n {COLORS[True]}Пароль угадан! Уровень пройден.{RESET} Выбран новый пароль.")
        return
    if turn.leaked:
        print(f"\n {YELLOW}Защитник проболтался: слово есть в ответе.{RESET}")
    print(f"\n {BOLD}{pipe.ghost_name}:{RESET} {turn.reply}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ghost", type=int, choices=(3, 4, 5), default=3)
    parser.add_argument("--tier", type=int, choices=(1, 2, 3, 4), default=1)
    parser.add_argument("--preload", action="store_true")
    args = parser.parse_args()
    os.system("")  # включает цвета в консоли Windows

    pipe = Pipeline(args.ghost, args.tier)
    try:
        print(f"Шлюз и мини-LLM: {pipe.service} | защитники по ступеням: {pipe.tiers}")
        if args.preload:
            for key in (pipe.service, pipe.defender[0]):
                pipe.server(key)
            pipe.general_bert()
        while True:
            print(f"\n{DIM}призрак {pipe.ghost} ({pipe.ghost_name}), ступень {pipe.tier}: {pipe.defender[0]} / {pipe.defender[1]}{RESET}")
            try:
                text = input("Вы: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            command, _, value = text.partition(" ")
            if command == "/exit":
                break
            elif command == "/help":
                print(__doc__)
            elif command == "/pw":
                print(f"Пароль: {pipe.password}")
            elif command == "/ghost" and value in ("3", "4", "5"):
                pipe.set_ghost(int(value))
            elif command == "/tier" and value in ("1", "2", "3", "4"):
                pipe.tier = int(value)
            elif command.startswith("/"):
                print("Не понял команду, /help покажет список.")
            else:
                show(pipe.ask(text), pipe)
    finally:
        pipe.close()


if __name__ == "__main__":
    main()
