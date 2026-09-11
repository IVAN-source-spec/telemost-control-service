from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AuthError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def safe_return_to(value: str | None) -> str:
    return value if value and value.startswith("/") and not value.startswith("//") else "/"


@dataclass(frozen=True)
class AuthSession:
    email: str
    name: str
    yandex_id: str
    is_admin: bool
    expires_at: int


class AuthUserStore:
    def __init__(self, database_url: str) -> None:
        prefix = "sqlite:///"
        if not database_url.startswith(prefix) or database_url == prefix:
            raise RuntimeError("AUTH_DATABASE_URL must contain a sqlite:/// path")
        self.path = Path(database_url[len(prefix) :])

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self, emails: set[str], admins: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS authorized_users (
                email TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1,
                is_admin INTEGER NOT NULL DEFAULT 0, display_name TEXT,
                yandex_id TEXT, created_at INTEGER NOT NULL, last_login_at INTEGER)"""
            )
            now = int(time.time())
            for email in sorted(emails | admins):
                connection.execute(
                    """INSERT INTO authorized_users (email, active, is_admin, created_at)
                    VALUES (?, 1, ?, ?) ON CONFLICT(email) DO UPDATE SET
                    active=1, is_admin=MAX(authorized_users.is_admin, excluded.is_admin)""",
                    (email, int(email in admins), now),
                )
            connection.commit()

    def get(self, email: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT email, is_admin FROM authorized_users WHERE email=? AND active=1",
                (email.strip().lower(),),
            ).fetchone()

    def record_login(self, email: str, name: str, yandex_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE authorized_users SET display_name=?, yandex_id=?, last_login_at=? WHERE email=?",
                (name, yandex_id, int(time.time()), email),
            )
            connection.commit()


class YandexOAuthService:
    authorize_url = "https://oauth.yandex.ru/authorize"
    token_url = "https://oauth.yandex.ru/token"
    user_info_url = "https://login.yandex.ru/info?format=json"

    def __init__(self) -> None:
        self.enabled = _flag("AUTH_ENABLED")
        self.client_id = os.getenv("YANDEX_AUTH_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("YANDEX_AUTH_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("YANDEX_AUTH_REDIRECT_URI", "").strip()
        self.secret = os.getenv("AUTH_SESSION_SECRET", "").strip()
        self.session_ttl = max(300, int(os.getenv("AUTH_SESSION_TTL_SECONDS", "43200")))
        self.state_ttl = max(60, int(os.getenv("AUTH_STATE_TTL_SECONDS", "600")))
        self.cookie_secure = _flag("AUTH_COOKIE_SECURE", True)
        self.session_cookie = os.getenv("AUTH_SESSION_COOKIE", "telemost_control_session")
        self.state_cookie = os.getenv("AUTH_STATE_COOKIE", "telemost_control_oauth_state")
        self.store = AuthUserStore(os.getenv(
            "AUTH_DATABASE_URL", "sqlite:////app/data/control_auth.sqlite3"
        ))
        self.bootstrap_emails = self._email_set("AUTH_BOOTSTRAP_EMAILS")
        self.bootstrap_admins = self._email_set("AUTH_BOOTSTRAP_ADMIN_EMAILS")

    @staticmethod
    def _email_set(name: str) -> set[str]:
        return {value.strip().lower() for value in os.getenv(name, "").split(",") if value.strip()}

    def initialize(self) -> None:
        if self.enabled:
            missing = [name for name, value in (
                ("YANDEX_AUTH_CLIENT_ID", self.client_id),
                ("YANDEX_AUTH_CLIENT_SECRET", self.client_secret),
                ("YANDEX_AUTH_REDIRECT_URI", self.redirect_uri),
                ("AUTH_SESSION_SECRET", self.secret),
            ) if not value]
            if missing:
                raise RuntimeError("Missing auth settings: " + ", ".join(missing))
            if len(self.secret) < 32:
                raise RuntimeError("AUTH_SESSION_SECRET must be at least 32 characters")
        self.store.initialize(self.bootstrap_emails, self.bootstrap_admins)

    def _sign(self, payload: dict[str, Any], purpose: str) -> str:
        encoded = _encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
        signature = hmac.new(
            self.secret.encode(), f"{purpose}.{encoded}".encode(), hashlib.sha256
        ).digest()
        return f"{encoded}.{_encode(signature)}"

    def _verify(self, token: str, purpose: str) -> dict[str, Any] | None:
        try:
            encoded, supplied = token.split(".", 1)
            expected = hmac.new(
                self.secret.encode(), f"{purpose}.{encoded}".encode(), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(expected, _decode(supplied)):
                return None
            payload = json.loads(_decode(encoded))
            return payload if int(payload.get("exp", 0)) > int(time.time()) else None
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    def create_state(self, return_to: str | None) -> str:
        now = int(time.time())
        return self._sign({
            "nonce": secrets.token_urlsafe(24), "return_to": safe_return_to(return_to),
            "iat": now, "exp": now + self.state_ttl,
        }, "oauth-state")

    def validate_state(self, state: str, cookie_state: str | None) -> str:
        if not cookie_state or not hmac.compare_digest(state, cookie_state):
            raise AuthError("invalid_state", "Состояние OAuth не совпало. Начните вход заново.")
        payload = self._verify(state, "oauth-state")
        if payload is None:
            raise AuthError("expired_state", "Срок действия запроса истёк. Начните вход заново.")
        return safe_return_to(str(payload.get("return_to", "/")))

    def authorization_url(self, state: str) -> str:
        return self.authorize_url + "?" + urllib.parse.urlencode({
            "response_type": "code", "client_id": self.client_id,
            "redirect_uri": self.redirect_uri, "state": state, "force_confirm": "yes",
        })

    def _request_json(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise AuthError("yandex_rejected", "Яндекс отклонил запрос авторизации.", 502) from exc
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            raise AuthError("yandex_unavailable", "Яндекс OAuth временно недоступен.", 502) from exc

    def exchange_code(self, code: str) -> str:
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code", "code": code,
            "client_id": self.client_id, "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }).encode()
        result = self._request_json(urllib.request.Request(
            self.token_url, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
        ))
        token = str(result.get("access_token", "")).strip()
        if not token:
            raise AuthError("missing_token", "Яндекс не вернул OAuth-токен.", 502)
        return token

    def fetch_user(self, token: str) -> dict[str, Any]:
        return self._request_json(urllib.request.Request(
            self.user_info_url, headers={"Authorization": f"OAuth {token}"}, method="GET",
        ))

    def authorize(self, user: dict[str, Any]) -> AuthSession:
        email = str(user.get("default_email") or user.get("login") or "").strip().lower()
        if not email:
            raise AuthError("email_missing", "Яндекс не вернул email пользователя.", 403)
        registered = self.store.get(email)
        if registered is None:
            raise AuthError("not_registered", "Пользователь не зарегистрирован в системе.", 403)
        name = str(user.get("display_name") or user.get("real_name") or email).strip()
        yandex_id = str(user.get("id", "")).strip()
        self.store.record_login(email, name, yandex_id)
        return AuthSession(email, name, yandex_id, bool(registered["is_admin"]), int(time.time()) + self.session_ttl)

    def create_session(self, session: AuthSession) -> str:
        now = int(time.time())
        return self._sign({
            "email": session.email, "name": session.name, "yandex_id": session.yandex_id,
            "is_admin": session.is_admin, "iat": now, "exp": now + self.session_ttl,
        }, "browser-session")

    def parse_session(self, token: str | None) -> AuthSession | None:
        if not self.enabled or not token:
            return None
        payload = self._verify(token, "browser-session")
        if payload is None:
            return None
        email = str(payload.get("email", "")).lower()
        registered = self.store.get(email)
        if registered is None:
            return None
        return AuthSession(
            email, str(payload.get("name", email)), str(payload.get("yandex_id", "")),
            bool(registered["is_admin"]), int(payload["exp"]),
        )
