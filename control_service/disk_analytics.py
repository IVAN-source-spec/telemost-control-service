from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any

from .analytics import MeetingRepository


LOGGER = logging.getLogger(__name__)
DISK_API_BASE = "https://cloud-api.yandex.net/v1/disk/resources"
DEFAULT_DISK_BASE_PATH = "/Материалы встреч/Telemost Bot"
EMPTY_MARKER_RE = re.compile(r"^recording_meeting_pyannote_.+_no_speech\.txt$", re.IGNORECASE)


class YandexDiskReadError(RuntimeError):
    pass


class YandexDiskReader:
    def __init__(self, token: str, timeout_seconds: int = 60) -> None:
        self.token = token
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def normalize_path(path: str) -> str:
        value = str(path or "").strip()
        if value.startswith("disk:"):
            value = value.removeprefix("disk:")
        if not value.startswith("/"):
            value = "/" + value
        return value.rstrip("/") or "/"

    def _request_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"OAuth {self.token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {}
            detail = error.read().decode("utf-8", errors="replace")
            raise YandexDiskReadError(
                f"Yandex Disk HTTP {error.code} {error.reason}: {detail}"
            ) from error
        except Exception as error:
            raise YandexDiskReadError(str(error)) from error

    def list_directory(self, path: str) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "path": "disk:" + self.normalize_path(path),
                "limit": "1000",
                "fields": "_embedded.items.name,_embedded.items.path,_embedded.items.type,_embedded.items.size",
            }
        )
        resource = self._request_json(f"{DISK_API_BASE}?{params}")
        return list(((resource.get("_embedded") or {}).get("items") or []))

    def download_json(self, path: str) -> dict[str, Any]:
        params = urllib.parse.urlencode({"path": "disk:" + self.normalize_path(path)})
        download = self._request_json(f"{DISK_API_BASE}/download?{params}")
        href = download.get("href")
        if not href:
            raise YandexDiskReadError(f"Download link not found: {path}")
        try:
            with urllib.request.urlopen(href, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise YandexDiskReadError(f"Could not download {path}: {error}") from error


def _normalized_title(value: Any) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(value or ""))
    return " ".join(text.casefold().split()).strip(". ")[:90].strip(". ")


def _parse_actual_start(value: Any, repository: MeetingRepository) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=repository.timezone)
    return parsed.astimezone(repository.timezone)


def match_disk_folder(
    meeting_time: dict[str, Any],
    candidates: list[dict[str, Any]],
    repository: MeetingRepository,
    used_meeting_ids: set[int],
) -> dict[str, Any] | None:
    disk_start = _parse_actual_start(
        meeting_time.get("started_at_astrakhan") or meeting_time.get("started_at"),
        repository,
    )
    disk_title = _normalized_title(meeting_time.get("title"))
    if disk_start is None or not disk_title:
        return None

    ranked: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        meeting_id = int(candidate["id"])
        if meeting_id in used_meeting_ids:
            continue
        candidate_start = _parse_actual_start(candidate.get("actual_start_at"), repository)
        if candidate_start is None:
            continue
        difference = abs((candidate_start - disk_start).total_seconds())
        if difference > 300:
            continue
        if _normalized_title(candidate.get("title")) != disk_title:
            continue
        ranked.append((difference, candidate))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


class MeetingDiskAnalyticsScanner:
    def __init__(
        self,
        repository: MeetingRepository,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.now_provider = now_provider or (lambda: datetime.now(self.repository.timezone))
        self.interval_seconds = max(
            60,
            int(os.getenv("YANDEX_DISK_ANALYTICS_INTERVAL_SECONDS", "3600")),
        )
        self.daily_audit_days = max(
            1,
            min(31, int(os.getenv("YANDEX_DISK_DAILY_AUDIT_DAYS", "7"))),
        )
        self.base_path = os.getenv("YANDEX_DISK_BASE_PATH", DEFAULT_DISK_BASE_PATH).strip()
        self.token = os.getenv("YANDEX_DISK_TOKEN", "").strip().strip('"')
        self.last_run: dict[str, Any] = {
            "status": "not_started",
            "started_at": None,
            "finished_at": None,
            "meeting_date": None,
            "candidates": 0,
            "folders_seen": 0,
            "matched": 0,
            "empty": 0,
            "not_empty": 0,
            "folders_present": 0,
            "folders_missing": 0,
            "errors": [],
        }
        self.last_daily_audit: dict[str, Any] = {
            "status": "not_started",
            "started_at": None,
            "finished_at": None,
            "date_from": None,
            "date_to": None,
            "days": self.daily_audit_days,
            "meetings_checked": 0,
            "folders_present": 0,
            "folders_missing": 0,
            "errors": [],
        }
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.scan_once()
            except Exception:
                LOGGER.exception("Yandex Disk meeting analytics scan failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def run_daily_audit_forever(self) -> None:
        while not self._stop_event.is_set():
            now = self.now_provider().astimezone(self.repository.timezone)
            next_midnight = datetime.combine(
                now.date() + timedelta(days=1),
                time.min,
                tzinfo=self.repository.timezone,
            )
            timeout = max(1.0, (next_midnight - now).total_seconds())
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=timeout)
                continue
            except asyncio.TimeoutError:
                pass
            try:
                await self.audit_previous_week()
            except Exception:
                LOGGER.exception("Yandex Disk seven-day audit failed")

    def stop(self) -> None:
        self._stop_event.set()

    async def scan_once(self) -> dict[str, Any]:
        async with self._lock:
            result = await asyncio.to_thread(self._scan_once_sync)
            self.last_run = result
            return result

    async def audit_previous_week(self) -> dict[str, Any]:
        async with self._lock:
            result = await asyncio.to_thread(self._audit_previous_week_sync)
            self.last_daily_audit = result
            return result

    def _scan_once_sync(
        self,
        meeting_date: date | None = None,
        *,
        final_check: bool = False,
    ) -> dict[str, Any]:
        started = self.now_provider().astimezone(self.repository.timezone)
        target_date = meeting_date or started.date()
        run = {
            "status": "completed",
            "started_at": started.isoformat(),
            "finished_at": None,
            "meeting_date": target_date.isoformat(),
            "final_check": final_check,
            "candidates": 0,
            "folders_seen": 0,
            "matched": 0,
            "empty": 0,
            "not_empty": 0,
            "folders_present": 0,
            "folders_missing": 0,
            "errors": [],
        }
        candidates = self.repository.disk_candidates(target_date, include_checked=True)
        run["candidates"] = len(candidates)
        day_path = (
            YandexDiskReader.normalize_path(self.base_path)
            + f"/{target_date:%Y/%m/%d}"
        )
        if not self.token:
            run["status"] = "configuration_error"
            run["errors"].append("YANDEX_DISK_TOKEN is not configured")
            run["finished_at"] = datetime.now(self.repository.timezone).isoformat()
            return run

        reader = YandexDiskReader(self.token)
        try:
            day_items = reader.list_directory(day_path)
        except Exception as error:
            run["status"] = "completed_with_errors"
            run["errors"].append(str(error))
            run["finished_at"] = datetime.now(self.repository.timezone).isoformat()
            return run

        folders = [
            item
            for item in day_items
            if item.get("type") == "dir" and not str(item.get("name") or "").startswith(".")
        ]
        run["folders_seen"] = len(folders)
        used_meeting_ids: set[int] = set()
        for folder in folders:
            folder_path = str(folder.get("path") or "")
            try:
                files = reader.list_directory(folder_path)
                marker_found = any(
                    item.get("type") == "file"
                    and EMPTY_MARKER_RE.match(str(item.get("name") or ""))
                    for item in files
                )
                meeting_time_item = next(
                    (
                        item
                        for item in files
                        if item.get("type") == "file" and item.get("name") == "meeting_time.json"
                    ),
                    None,
                )
                if meeting_time_item is None:
                    continue
                meeting_time = reader.download_json(str(meeting_time_item.get("path") or ""))
                candidate = match_disk_folder(
                    meeting_time,
                    candidates,
                    self.repository,
                    used_meeting_ids,
                )
                if candidate is None:
                    continue
                meeting_id = int(candidate["id"])
                used_meeting_ids.add(meeting_id)
                status = "empty" if marker_found else "not_empty"
                self.repository.update_disk_result(
                    meeting_id=meeting_id,
                    status=status,
                    folder_path=YandexDiskReader.normalize_path(folder_path),
                    marker_found=marker_found,
                    completed=True,
                    folder_exists=True,
                )
                run["matched"] += 1
                run[status] += 1
                run["folders_present"] += 1
            except Exception as error:
                run["errors"].append(f"{folder.get('name')}: {error}")

        for candidate in candidates:
            meeting_id = int(candidate["id"])
            if meeting_id in used_meeting_ids:
                continue
            if run["errors"]:
                continue
            previous_empty_status = str(candidate.get("disk_empty_status") or "unknown")
            keep_empty_result = previous_empty_status in {"empty", "not_empty"}
            self.repository.update_disk_result(
                meeting_id=meeting_id,
                status=(
                    previous_empty_status
                    if keep_empty_result
                    else "folder_not_found" if final_check else "unknown"
                ),
                folder_path=None,
                marker_found=bool(candidate.get("empty_marker_found")) if keep_empty_result else False,
                completed=bool(candidate.get("disk_scan_completed")) if keep_empty_result else False,
                folder_exists=False,
            )
            run["folders_missing"] += 1
        if run["errors"]:
            run["status"] = "completed_with_errors"
        run["finished_at"] = datetime.now(self.repository.timezone).isoformat()
        return run

    def _audit_previous_week_sync(self) -> dict[str, Any]:
        started = self.now_provider().astimezone(self.repository.timezone)
        date_to = started.date() - timedelta(days=1)
        date_from = date_to - timedelta(days=self.daily_audit_days - 1)
        audit = {
            "status": "completed",
            "started_at": started.isoformat(),
            "finished_at": None,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "days": self.daily_audit_days,
            "meetings_checked": 0,
            "folders_present": 0,
            "folders_missing": 0,
            "errors": [],
            "results": [],
        }
        for offset in range(self.daily_audit_days):
            target_date = date_from + timedelta(days=offset)
            result = self._scan_once_sync(target_date, final_check=True)
            audit["results"].append(result)
            audit["meetings_checked"] += int(result["candidates"])
            audit["folders_present"] += int(result["folders_present"])
            audit["folders_missing"] += int(result["folders_missing"])
            audit["errors"].extend(
                f"{target_date.isoformat()}: {error}" for error in result["errors"]
            )
        if audit["errors"]:
            audit["status"] = "completed_with_errors"
        audit["finished_at"] = datetime.now(self.repository.timezone).isoformat()
        return audit
