import json
from dataclasses import asdict


class LogObserver:
    def __init__(self, path: str):
        self.path = path

    def __call__(self, event):
        data = {"type": type(event).__name__, **asdict(event)}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")