import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def read_json_file(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def prune_dispatch_state(state: dict, keep_hours: int) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, keep_hours))
    dispatched = state.setdefault("dispatched", {})
    retained = {}
    for event_id, record in dispatched.items():
        candidates = (
            record.get("last_attempt_at"),
            record.get("dispatched_at"),
            record.get("starts_at"),
        )
        stamp = next((parse_iso_datetime(value) for value in candidates if parse_iso_datetime(value)), None)
        if stamp is None or stamp.astimezone(timezone.utc) >= cutoff:
            retained[event_id] = record
    state["dispatched"] = retained
    return state
