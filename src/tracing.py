"""Trace JSONL de chaque exécution : une ligne par événement."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from src import config


class Tracer:
    def __init__(self, level: int, question: str, directory: Path | None = None) -> None:
        directory = directory or config.TRACES_DIR
        self.run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{self.run_id}.jsonl"
        self.t0 = time.perf_counter()
        self.log("start", level=level, question=question)

    @classmethod
    def attach(cls, path: Path | str) -> "Tracer":
        """Reprend une trace existante (ex. validation d'une action après la fin de la boucle)."""
        tracer = cls.__new__(cls)
        tracer.path, tracer.run_id, tracer.t0 = Path(path), Path(path).stem, time.perf_counter()
        return tracer

    def log(self, event: str, **data: Any) -> None:
        line = {"run_id": self.run_id, "t": round(time.perf_counter() - self.t0, 3), "event": event, **data}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
