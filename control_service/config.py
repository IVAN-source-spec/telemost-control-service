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
        os.environ.setdefault(key.strip(), raw.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class BotNodeConfig:
    id: str
    name: str
    base_url: str
    token: str = ""
    machine_id: str = ""
    machine_name: str = ""
    lifecycle: str = "persistent"
    provider: str = ""
    public_ip: str = ""


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

    return [
        BotNodeConfig(
            id=str(item["id"]),
            name=str(item.get("name") or item["id"]),
            base_url=str(item["base_url"]).rstrip("/"),
            token=str(item.get("token") or ""),
            machine_id=str(item.get("machine_id") or ""),
            machine_name=str(item.get("machine_name") or ""),
            lifecycle=str(item.get("lifecycle") or "persistent"),
            provider=str(item.get("provider") or ""),
            public_ip=str(item.get("public_ip") or ""),
        )
        for item in payload
    ]


def control_token_required() -> bool:
    return os.getenv("CONTROL_SERVICE_REQUIRE_API_TOKEN", "0").lower() in ("1", "true", "yes")


def control_api_token() -> str:
    return os.getenv("CONTROL_SERVICE_API_TOKEN", "")


def session_validator_url() -> str:
    return os.getenv("SESSION_VALIDATOR_URL", "http://127.0.0.1:8050").rstrip("/")


def assignment_service_url() -> str:
    return os.getenv("ASSIGNMENT_SERVICE_URL", "http://127.0.0.1:8040").rstrip("/")


def assignment_service_api_token() -> str:
    return os.getenv("ASSIGNMENT_SERVICE_API_TOKEN", "").strip()
