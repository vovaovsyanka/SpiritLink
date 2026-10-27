"""
Поддельный llama-server для тестов: тот же HTTP-интерфейс (/health, /v1/chat/completions), без модели.
Настраивается переменными окружения:
  FAKE_LLAMA_DELAY  пауза на каждый запрос, с
  FAKE_LLAMA_LOAD   сколько секунд после запуска /health отвечает 503 («модель ещё грузится»)
  FAKE_LLAMA_FAIL   ключи моделей через запятую, которые завершаются при старте
/stats отдаёт число обработанных запросов и максимум одновременных.
"""

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--key", default="")
args = parser.parse_args()

if args.key and args.key in os.environ.get("FAKE_LLAMA_FAIL", "").split(","):
    print("fake-llama: завершаюсь при старте", flush=True)
    sys.exit(3)

DELAY = float(os.environ.get("FAKE_LLAMA_DELAY", "0"))
LOAD = float(os.environ.get("FAKE_LLAMA_LOAD", "0"))
STARTED = time.time()
STATS = {"now": 0, "max": 0, "total": 0}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200 if time.time() - STARTED >= LOAD else 503, {"status": "ok"})
        elif self.path == "/stats":
            self._send(200, {"total": STATS["total"], "max_concurrent": STATS["max"]})
        else:
            self._send(404, {})

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with LOCK:
            STATS["now"] += 1
            STATS["total"] += 1
            STATS["max"] = max(STATS["max"], STATS["now"])
        time.sleep(DELAY)
        with LOCK:
            STATS["now"] -= 1
        user = request["messages"][-1]["content"]
        content = f"<think>скрытые рассуждения</think>эхо[{args.key}]: {user}"
        self._send(200, {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": len(user), "completion_tokens": 5}})


ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
