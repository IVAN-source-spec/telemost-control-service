from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any


class EmployeeDirectoryError(RuntimeError):
    pass


class EmployeeDirectoryClient:
    def __init__(self) -> None:
        self.url = os.getenv(
            "EMPLOYEE_DIRECTORY_URL", "https://lk.razum.life/api/v2/users/"
        ).strip()
        self.token = os.getenv("EMPLOYEE_DIRECTORY_TOKEN", "").strip()
        self.timeout_seconds = float(os.getenv("EMPLOYEE_DIRECTORY_TIMEOUT_SECONDS", "15"))
        self.cache_ttl_seconds = max(
            30, int(os.getenv("EMPLOYEE_DIRECTORY_CACHE_TTL_SECONDS", "600"))
        )
        self.page_size = max(
            1, min(100, int(os.getenv("EMPLOYEE_DIRECTORY_PAGE_SIZE", "100")))
        )
        self._lock = threading.Lock()
        self._users: list[dict[str, Any]] = []
        self._expires_at = 0.0
        self._refreshed_at = 0.0

    def _request_page(self, page: int) -> dict[str, Any]:
        if not self.token:
            raise EmployeeDirectoryError("EMPLOYEE_DIRECTORY_TOKEN is not configured")
        request = urllib.request.Request(
            self.url,
            data=json.dumps(
                {"page": page, "page_size": self.page_size, "is_active": True}
            ).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise EmployeeDirectoryError(
                f"Employee directory returned HTTP {error.code}: {body[:300]}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise EmployeeDirectoryError(f"Employee directory is unavailable: {error}") from error
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise EmployeeDirectoryError("Employee directory returned invalid JSON") from error
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise EmployeeDirectoryError("Employee directory returned an unsuccessful response")
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("users"), list):
            raise EmployeeDirectoryError("Employee directory response has an invalid structure")
        return data

    @staticmethod
    def _public_user(item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict) or item.get("is_active") is False:
            return None
        email = str(item.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return None
        full_name = str(item.get("full_name") or "").strip()
        if not full_name:
            full_name = " ".join(
                part
                for part in (
                    str(item.get("first_name") or "").strip(),
                    str(item.get("last_name") or "").strip(),
                )
                if part
            )
        return {
            "id": item.get("id"),
            "full_name": full_name or email,
            "email": email,
            "position": str(item.get("position") or "").strip(),
            "organization": str(item.get("organization") or "").strip(),
        }

    def _fetch_all(self) -> list[dict[str, Any]]:
        first = self._request_page(1)
        pages = max(1, int(first.get("total_pages") or 1))
        raw_users = list(first.get("users") or [])
        for page in range(2, pages + 1):
            raw_users.extend(self._request_page(page).get("users") or [])
        users_by_email: dict[str, dict[str, Any]] = {}
        for item in raw_users:
            user = self._public_user(item)
            if user is not None:
                users_by_email[user["email"]] = user
        return sorted(
            users_by_email.values(),
            key=lambda user: (user["full_name"].casefold(), user["email"]),
        )

    def list_active(self, force: bool = False) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            if self._users and not force and now < self._expires_at:
                return {
                    "users": list(self._users),
                    "count": len(self._users),
                    "cached": True,
                    "stale": False,
                    "refreshed_at": self._refreshed_at,
                }
            try:
                users = self._fetch_all()
            except EmployeeDirectoryError as error:
                if self._users:
                    return {
                        "users": list(self._users),
                        "count": len(self._users),
                        "cached": True,
                        "stale": True,
                        "refreshed_at": self._refreshed_at,
                        "warning": str(error),
                    }
                raise
            self._users = users
            self._refreshed_at = now
            self._expires_at = now + self.cache_ttl_seconds
            return {
                "users": list(users),
                "count": len(users),
                "cached": False,
                "stale": False,
                "refreshed_at": self._refreshed_at,
            }
