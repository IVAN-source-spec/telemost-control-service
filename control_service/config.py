import json
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        key = key.strip()
        raw = raw.strip().strip('"').strip("'")
        os.environ.setdefault(key, raw)


@dataclass(frozen=True)
class BotNodeConfig:
    id: str
    name: str
    base_url: str
    token: str = ""


def load_nodes() -> list[BotNodeConfig]:
    raw_json = os.getenv("BOT_NODES_JSON", "").strip()
    if raw_json:
        payload = json.loads(raw_json)
    else:
        config_path = Path(os.getenv("BOT_NODES_CONFIG", "config/nodes.json"))
        if not config_path.is_absolute():
            config_path = PROJECT_ROOT / config_path
        if not config_path.exists():
            return []
        payload = json.loads(config_path.read_text(encoding="utf-8"))

    nodes = []
    for item in payload:
        nodes.append(
            BotNodeConfig(
                id=str(item["id"]),
                name=str(item.get("name") or item["id"]),
                base_url=str(item["base_url"]).rstrip("/"),
                token=str(item.get("token") or ""),
            )
        )
    return nodes


def control_token_required() -> bool:
    return os.getenv("CONTROL_SERVICE_REQUIRE_API_TOKEN", "0").lower() in ("1", "true", "yes")


def control_api_token() -> str:
    return os.getenv("CONTROL_SERVICE_API_TOKEN", "")
