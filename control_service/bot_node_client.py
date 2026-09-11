import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from typing import Any

from .config import BotNodeConfig


class BotNodeError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class BotNodeClient:
    def __init__(self, node: BotNodeConfig, timeout_seconds: int = 20):
        self.node = node
        self.timeout_seconds = timeout_seconds

    def request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = self.node.base_url + path
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.node.token:
            headers["Authorization"] = f"Bearer {self.node.token}"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8")) if body else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise BotNodeError(f"{self.node.id} HTTP {error.code}: {detail}", status_code=error.code) from error
        except Exception as error:
            raise BotNodeError(f"{self.node.id}: {error}") from error

    def status(self) -> dict:
        configured = asdict(self.node)
        try:
            data = self.request_json("GET", "/api/v1/node/status")
            data.setdefault("node_id", self.node.id)
            data.setdefault("node_name", self.node.name)
            data.setdefault("base_url", self.node.base_url)
            data["configured_node"] = configured
            return data
        except Exception as error:
            placeholder_bots = []
            if self.node.lifecycle == "on_demand":
                placeholder_bots = [
                    {
                        "bot_id": "test-bot-1",
                        "global_bot_id": f"{self.node.id}:test-bot-1",
                        "status": "unavailable",
                        "configured_placeholder": True,
                        "title": None,
                        "meeting_url": None,
                        "started_at": None,
                    }
                ]
            return {
                "node_id": self.node.id,
                "node_name": self.node.name,
                "base_url": self.node.base_url,
                "configured_node": configured,
                "status": "unavailable",
                "error": str(error),
                "bots_total": 0,
                "bots_idle": 0,
                "bots_busy": 0,
                "bots": placeholder_bots,
            }

    def create_meeting_any_bot(self, payload: dict[str, Any]) -> dict:
        return self.request_json("POST", "/api/v1/bots/meetings", payload)

    def create_meeting_for_bot(self, bot_id: str, payload: dict[str, Any]) -> dict:
        safe_bot_id = urllib.parse.quote(bot_id, safe="")
        return self.request_json("POST", f"/api/v1/bots/{safe_bot_id}/meetings", payload)

    def leave_meeting(self, bot_id: str, payload: dict) -> dict:
        safe_bot_id = urllib.parse.quote(bot_id, safe="")
        return self.request_json("POST", f"/api/v1/bots/{safe_bot_id}/leave", payload)

    def list_meeting_tasks(self) -> dict:
        return self.request_json("GET", "/api/v1/meetings/")

    def agenda_status(self, bot_id: str) -> dict:
        safe_bot_id = urllib.parse.quote(bot_id, safe="")
        return self.request_json("GET", f"/api/v1/bots/{safe_bot_id}/agenda/status")

    def activate_agenda(self, bot_id: str, payload: dict[str, Any]) -> dict:
        safe_bot_id = urllib.parse.quote(bot_id, safe="")
        return self.request_json("POST", f"/api/v1/bots/{safe_bot_id}/agenda/activate", payload)

    def audio_monitor(self, bot_id: str, payload: dict) -> dict:
        safe_bot_id = urllib.parse.quote(bot_id, safe="")
        return self.request_json("POST", f"/api/v1/bots/{safe_bot_id}/audio-monitor", payload)
