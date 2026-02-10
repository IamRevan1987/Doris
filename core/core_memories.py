from __future__ import annotations
from typing import Iterable, List, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import json

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def append_turn(
        path: Path,
        role: str,
        content: str,
        meta: Dict[str, Any] | None = None,
) -> None:
        path.parent.mkdir(parents = True, exist_ok = True)
        record = {
            "ts": _now_iso(),
            "role": role,
            "content": content,
            "meta": meta or {},
        }

        with path.open("a", encoding = "utf-8") as f:
            f.write(json.dumps(record, ensure_ascii = False) + "\n")


def load_turns(path: Path, limit: int = 200) -> List[Dict[str , Any]]:
    if not path.exists:
        return []
    turns: List[Dict[str, Any]] = []
    with path.open("r", encoding = "utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip corrupted lines rather than killing the app
                continue
    return turns[-limit:]
