"""
PC Guardian — Keyword Listener
Global keyboard hook — detects lock keyword typed anywhere
"""

import logging
from pynput import keyboard
from logs.logger import log_event

logger = logging.getLogger("keyword_listener")


class KeywordListener:
    def __init__(self, cfg, lock_engine):
        self.cfg = cfg
        self.lock_engine = lock_engine
        self._buffer = []
        self._listener = None

    def start(self):
        logger.info(f"Keyword listener active. Keyword: {self.cfg.lock_keyword}")
        with keyboard.Listener(on_press=self._on_press) as listener:
            self._listener = listener
            listener.join()

    def _on_press(self, key):
        keyword = self.cfg.lock_keyword.lower()
        try:
            char = key.char
            if char:
                self._buffer.append(char.lower())
                # Keep buffer at keyword length
                if len(self._buffer) > len(keyword):
                    self._buffer.pop(0)
                # Check match
                if "".join(self._buffer) == keyword:
                    self._buffer.clear()
                    logger.info("Lock keyword detected.")
                    log_event("KEYWORD_LOCK", "Lock triggered by keyword.")
                    self.lock_engine.lock()
        except AttributeError:
            # Special key — reset buffer
            self._buffer.clear()
