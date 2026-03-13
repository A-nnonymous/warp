from __future__ import annotations

import collections
import threading
from typing import Any

from .constants import STATE_DIR

PEEK_MAX_LINES = 200
PEEK_DIR = STATE_DIR / "peek"


class PeekMixin:
    """In-memory ring buffer per agent for real-time output peek, with file persistence."""

    def __init_peek(self) -> None:
        if not hasattr(self, "_peek_buffers"):
            self._peek_buffers: dict[str, collections.deque[str]] = {}
            self._peek_lock = threading.Lock()
            PEEK_DIR.mkdir(parents=True, exist_ok=True)

    def peek_append(self, agent: str, lines: list[str]) -> None:
        self.__init_peek()
        with self._peek_lock:
            buf = self._peek_buffers.get(agent)
            if buf is None:
                buf = collections.deque(maxlen=PEEK_MAX_LINES)
                self._peek_buffers[agent] = buf
            for line in lines:
                buf.append(line)
            self._persist_peek_file(agent, buf)

    def peek_read(self, agent: str) -> list[str]:
        self.__init_peek()
        with self._peek_lock:
            buf = self._peek_buffers.get(agent)
            if buf is not None:
                return list(buf)
        return self._load_peek_file(agent)

    def peek_read_all(self) -> dict[str, list[str]]:
        self.__init_peek()
        result: dict[str, list[str]] = {}
        with self._peek_lock:
            for agent, buf in self._peek_buffers.items():
                result[agent] = list(buf)
        for path in sorted(PEEK_DIR.glob("*.log")):
            agent = path.stem
            if agent not in result:
                result[agent] = self._load_peek_file(agent)
        return result

    def peek_clear(self, agent: str) -> None:
        self.__init_peek()
        with self._peek_lock:
            self._peek_buffers.pop(agent, None)
            path = PEEK_DIR / f"{agent}.log"
            if path.exists():
                path.unlink()

    def _persist_peek_file(self, agent: str, buf: collections.deque[str]) -> None:
        path = PEEK_DIR / f"{agent}.log"
        path.write_text("\n".join(buf) + "\n", encoding="utf-8")

    def _load_peek_file(self, agent: str) -> list[str]:
        path = PEEK_DIR / f"{agent}.log"
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) > PEEK_MAX_LINES:
            lines = lines[-PEEK_MAX_LINES:]
        return lines
