"""Format de sortie commun aux 4 niveaux : eval.py et l'interface ne lisent que ça."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Result:
    level: int
    answer: str = ""
    sources: list[str] = field(default_factory=list)    # ids cités dans la réponse
    retrieved: list[str] = field(default_factory=list)  # ids classés par la recherche
    abstained: bool = False
    clarified: bool = False
    refused: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None        # action en attente de confirmation
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    steps: int = 0
    stop_reason: str = "final"
    error: str | None = None
    trace_path: str | None = None                       # trace JSONL de l'exécution

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
