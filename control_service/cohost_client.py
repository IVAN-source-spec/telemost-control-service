from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class CohostServiceError(RuntimeError):
    pass


class CohostServiceClient:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "CALENDAR_DISCOVERY_URL", "http://127.0.0.1:8030"
        ).rstrip("/")
        self.token = os.getenv("CALENDAR_DISCOVERY_COHOST_TOKEN", "").strip()
        self.timeout_seconds = float(os.getenv("CALENDAR_COHOST_REQUEST_TIMEOUT_SECONDS", "10"))

    @property
    def enabled(self) -> bool:
        return os.getenv("CALENDAR_COHOST_ENABLED", "1").strip().lower() in {
            "1", "true", "yes", "on"
        }

    def _post(self, path: str, payload: dict) -> dict:
        if not self.enabled:
            return {"status": "disabled"}
        if not self.token:
            raise CohostServiceError("CALENDAR_DISCOVERY_COHOST_TOKEN is not configured")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise CohostServiceError(f"HTTP {error.code}: {body[:500]}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise CohostServiceError(f"Cohost service is unavailable: {error}") from error
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError as error:
            raise CohostServiceError("Cohost service returned invalid JSON") from error

    def ensure(self, meeting_url: str, organizer_email: str) -> dict:
        return self._post(
            "/api/v1/cohosts/ensure",
            {"meeting_url": meeting_url, "organizer_email": organizer_email},
        )

    def resolve_and_ensure(self, meeting_url: str) -> dict:
        return self._post(
            "/api/v1/cohosts/resolve-and-ensure",
            {"meeting_url": meeting_url},
        )
