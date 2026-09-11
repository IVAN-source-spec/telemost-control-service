from __future__ import annotations

import json
import urllib.error
import urllib.request


class SessionServiceError(RuntimeError):
    pass


class SessionServiceClient:
    def __init__(self, base_url: str, timeout_seconds: int = 90) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SessionServiceError(f"Session service HTTP {exc.code}: {detail[:500]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SessionServiceError(f"Session service is unavailable: {exc}") from exc
        parsed = json.loads(content) if content else {}
        if not isinstance(parsed, dict):
            raise SessionServiceError("Session service returned an invalid response")
        return parsed

    def state(self) -> dict[str, object]:
        return self._request("GET", "/api/v1/session/state")

    def check(self) -> dict[str, object]:
        return self._request("POST", "/api/v1/session/check")

    def confirm(self, code: str) -> dict[str, object]:
        return self._request("POST", "/api/v1/session/confirm", {"code": code})

    def configure_automatic_check(
        self, *, enabled: bool, interval_seconds: int
    ) -> dict[str, object]:
        return self._request(
            "POST",
            "/api/v1/session/automatic-check",
            {"enabled": enabled, "interval_seconds": interval_seconds},
        )
