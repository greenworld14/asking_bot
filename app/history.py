import json
import threading
from datetime import datetime

from .config import resolve


class History:
    def __init__(self, cfg):
        self.enabled = cfg.get("enabled", True)
        self.path = resolve(cfg["file"])
        self.lock = threading.Lock()

    def add(self, question, answer, source, kind=None, role=None):
        if not self.enabled:
            return
        row = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "type": kind,
            "interviewer": role,
            "question": question,
            "answer": answer,
        }
        try:
            with self.lock, open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass
