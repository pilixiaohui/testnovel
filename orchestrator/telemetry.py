from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .config import ORCHESTRATOR_EVENTS_FILE


def new_trace_id() -> str:
    return str(uuid.uuid4())


def log_event(event: str, *, trace_id: str, **fields: object) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "trace_id": trace_id,
        **fields,
    }
    ORCHESTRATOR_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ORCHESTRATOR_EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
