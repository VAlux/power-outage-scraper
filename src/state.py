import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass
class State:
    by_day_fingerprint: Dict[str, str]


def load_state(path: str) -> State:
    p = Path(path)
    if not p.exists():
        return State(by_day_fingerprint={})

    content = p.read_text(encoding="utf-8").strip()
    if not content:
        return State(by_day_fingerprint={})

    data = json.loads(content)
    return State(by_day_fingerprint=data.get("by_day_fingerprint", {}))


def save_state(path: str, state: State) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"by_day_fingerprint": state.by_day_fingerprint}, ensure_ascii=True),
        encoding="utf-8",
    )
