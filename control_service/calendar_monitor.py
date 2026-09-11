import asyncio
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .bot_node_client import BotNodeClient, BotNodeError
from .calendar_agenda import CalendarAgendaService
from .calendar_state import (
    prune_dispatch_state,
    read_json_file,
    resolve_project_path,
    write_json_file,
)
from .config import PROJECT_ROOT, load_nodes
from .dispatch_guard import active_assignment, meeting_dispatch_lock, normalize_meeting_url


try:
    DEFAULT_CALENDAR_TZ = ZoneInfo("Europe/Astrakhan")
except ZoneInfoNotFoundError:
    DEFAULT_CALENDAR_TZ = timezone(timedelta(hours=4), name="Europe/Astrakhan")

TELEMOST_RE = re.compile(r"https://telemost\.(?:360\.)?yandex\.ru/[^\s<>'\"\\]+", re.IGNORECASE)
AGENDA_BLOCK_RE = re.compile(r"###\s*Повестка\s*:\s*(.*?)\s*###", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class CalendarAttendee:
    name: str
    email: str | None = None
    partstat: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class CalendarEvent:
    uid: str
    title: str
    description: str
    location: str
    starts_at: datetime
    ends_at: datetime | None
    meeting_url: str
    calendar_source: str
    attendees: tuple[CalendarAttendee, ...] = ()
    organizer_attendee: CalendarAttendee | None = None


class CalendarMonitor:
    def __init__(self):
        self.enabled = os.getenv("CALENDAR_MONITOR_ENABLED", "0").lower() in ("1", "true", "yes")
        self.provider = os.getenv("CALENDAR_PROVIDER", "ics").strip().lower()
        self.poll_interval = int(os.getenv("CALENDAR_POLL_INTERVAL_SECONDS", "60"))
        self.join_before = timedelta(minutes=int(os.getenv("CALENDAR_JOIN_BEFORE_MINUTES", "2")))
        self.join_after_start = timedelta(minutes=int(os.getenv("CALENDAR_JOIN_AFTER_START_MINUTES", "30")))
        self.state_file = PROJECT_ROOT / os.getenv("CALENDAR_STATE_FILE", "data/calendar_seen.json")
        self.control_enabled = os.getenv("CALENDAR_SCHEDULER_ENABLED", "1").lower() in ("1", "true", "yes")
        self.lookahead_hours = int(os.getenv("CALENDAR_LOOKAHEAD_HOURS", "2"))
        self.missed_lookback = timedelta(minutes=int(os.getenv("CALENDAR_MISSED_LOOKBACK_MINUTES", "10")))
        self.dispatch_keep_hours = int(os.getenv("CALENDAR_DISPATCH_KEEP_HOURS", "24"))
        self.dynamic_agenda_enabled = os.getenv("CALENDAR_DYNAMIC_AGENDA_ENABLED", "1").lower() in ("1", "true", "yes")
        self.dynamic_agenda_interval = int(os.getenv("CALENDAR_DYNAMIC_AGENDA_POLL_SECONDS", "10"))
        self.upcoming_file = resolve_project_path(os.getenv("CALENDAR_UPCOMING_FILE", "data/calendar_upcoming.json"))
        self.dispatch_state_file = resolve_project_path(
            os.getenv("CALENDAR_DISPATCH_STATE_FILE", "data/calendar_dispatch_state.json")
        )
        self.timezone = self._timezone_from_env()
        self._stop_event = asyncio.Event()
        self._last_error: str | None = None
        self._last_checked_at: str | None = None
        self._last_dispatched_at: str | None = None
        self._tick_lock = asyncio.Lock()
        self._control_update_callbacks = []
        self._calendar_agendas = CalendarAgendaService()

    def add_control_update_callback(self, callback) -> None:
        self._control_update_callbacks.append(callback)

    def notify_control_schedule_changed(self) -> None:
        for callback in tuple(self._control_update_callbacks):
            try:
                callback()
            except Exception as error:
                print(f"[CalendarMonitor] Control update callback failed: {error}")

    @staticmethod
    def control_schedule_signature(payload: dict) -> tuple:
        return tuple(sorted(
            (
                str(item.get("event_id") or ""),
                str(item.get("starts_at") or ""),
                str(item.get("ends_at") or ""),
                str(item.get("meeting_url") or ""),
            )
            for item in payload.get("events") or []
            if item.get("meeting_url")
        ))

    def _timezone_from_env(self):
        name = os.getenv("CALENDAR_TIMEZONE", "Europe/Astrakhan")
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            return DEFAULT_CALENDAR_TZ

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "poll_interval_seconds": self.poll_interval,
            "join_before_minutes": int(self.join_before.total_seconds() // 60),
            "join_after_start_minutes": int(self.join_after_start.total_seconds() // 60),
            "ics_sources": len(self.ics_urls()),
            "caldav_url": os.getenv("CALENDAR_CALDAV_URL", ""),
            "caldav_username": os.getenv("CALENDAR_USERNAME", ""),
            "calendar_name": os.getenv("CALENDAR_NAME", ""),
            "last_checked_at": self._last_checked_at,
            "last_dispatched_at": self._last_dispatched_at,
            "last_error": self._last_error,
            "state_file": str(self.state_file),
            "scheduler": self.control_status(),
        }

    def control_status(self) -> dict:
        upcoming = self.read_upcoming()
        dispatch_state = self.read_dispatch_state()
        dispatched = dispatch_state.get("dispatched", {})
        return {
            "enabled": self.control_enabled,
            "lookahead_hours": self.lookahead_hours,
            "missed_lookback_minutes": int(self.missed_lookback.total_seconds() // 60),
            "dispatch_keep_hours": self.dispatch_keep_hours,
            "dynamic_agenda_enabled": self.dynamic_agenda_enabled,
            "dynamic_agenda_poll_seconds": self.dynamic_agenda_interval,
            "upcoming_file": str(self.upcoming_file),
            "dispatch_state_file": str(self.dispatch_state_file),
            "upcoming_generated_at": upcoming.get("generated_at"),
            "upcoming_events": len(upcoming.get("events") or []),
            "dispatch_records": len(dispatched),
            "dispatched_success": sum(1 for item in dispatched.values() if item.get("status") == "dispatched"),
            "dispatch_failed": sum(1 for item in dispatched.values() if item.get("status") == "failed"),
        }

    def ics_urls(self) -> list[str]:
        raw_json = os.getenv("CALENDAR_ICS_URLS", "").strip()
        if raw_json:
            try:
                payload = json.loads(raw_json)
                return [str(item).strip() for item in payload if str(item).strip()]
            except json.JSONDecodeError:
                pass

        raw = os.getenv("CALENDAR_ICS_URL", "").strip()
        if not raw:
            return []
        parts = re.split(r"[\n;,]+", raw)
        return [part.strip() for part in parts if part.strip()]

    def read_state(self) -> dict:
        if not self.state_file.exists():
            return {"dispatched": {}}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {"dispatched": {}}

    def write_state(self, state: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def stop(self) -> None:
        self._stop_event.set()
        self._calendar_agendas.stop()

    async def run_forever(self) -> None:
        if not self.enabled:
            print("[CalendarMonitor] Disabled")
            return
        if self.provider == "ics" and not self.ics_urls():
            print("[CalendarMonitor] CALENDAR_ICS_URL/CALENDAR_ICS_URLS is not configured")
            return
        if self.provider == "caldav" and not self.caldav_is_configured():
            print("[CalendarMonitor] CalDAV is not configured")
            return

        print("[CalendarMonitor] Started")
        while not self._stop_event.is_set():
            try:
                await self.tick()
                self._last_error = None
            except Exception as error:
                self._last_error = str(error)
                print(f"[CalendarMonitor] Tick failed: {error}")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass

    async def tick(self) -> None:
        async with self._tick_lock:
            self._last_checked_at = datetime.now(timezone.utc).isoformat()
            events = self.deduplicate_occurrences(await self.fetch_events())
            now = datetime.now(timezone.utc)

            if self.control_enabled:
                await self.update_calendar_control(events, now)
                return

            state = self.read_state()
            dispatched = state.setdefault("dispatched", {})

            for event in sorted(events, key=lambda item: item.starts_at):
                external_event_id = f"calendar:{event.uid}"
                if external_event_id in dispatched:
                    continue
                if not self.should_dispatch(event, now):
                    continue

                result = await self.dispatch_event(event, external_event_id)
                dispatched[external_event_id] = {
                    "dispatched_at": datetime.now(timezone.utc).isoformat(),
                    "title": event.title,
                    "meeting_url": event.meeting_url,
                    "starts_at": event.starts_at.isoformat(),
                    "result": result,
                }
                self._last_dispatched_at = datetime.now(timezone.utc).isoformat()
                self.write_state(state)

    async def refresh_control_now(self) -> dict:
        async with self._tick_lock:
            self._last_checked_at = datetime.now(timezone.utc).isoformat()
            events = await self.fetch_events()
            now = datetime.now(timezone.utc)
            await self.update_calendar_control(events, now)
            self._last_error = None
            return self.read_upcoming()

    async def update_calendar_control(self, events: list[CalendarEvent], now: datetime) -> None:
        previous_schedule = self.control_schedule_signature(self.read_upcoming())
        events = self.deduplicate_occurrences(events)
        relevant_events = sorted(
            [event for event in events if self.event_is_in_control_window(event, now)],
            key=lambda item: item.starts_at,
        )
        dispatch_state = prune_dispatch_state(self.read_dispatch_state(), self.dispatch_keep_hours)
        dispatched = dispatch_state.setdefault("dispatched", {})

        event_rows = []
        for event in relevant_events:
            event_id = self.external_event_id(event)
            row = self.event_to_row(event, event_id, dispatched.get(event_id), now)
            event_rows.append(row)

        upcoming_payload = {
            "generated_at": now.isoformat(),
            "range": {
                "start": now.isoformat(),
                "end": (now + timedelta(hours=self.lookahead_hours)).isoformat(),
            },
            "summary": self.upcoming_summary(event_rows),
            "events": event_rows,
        }
        self.write_upcoming(upcoming_payload)
        if self.control_schedule_signature(upcoming_payload) != previous_schedule:
            self.notify_control_schedule_changed()

        changed = False
        for event in relevant_events:
            if not event.meeting_url:
                continue
            if not self.should_dispatch_from_control(event, now):
                continue

            event_id = self.external_event_id(event)
            record = dispatched.get(event_id, {})
            if record.get("status") == "dispatched":
                continue
            if record.get("status") == "dispatching":
                continue

            attempt_at = datetime.now(timezone.utc).isoformat()
            record = {
                **record,
                "event_id": event_id,
                "status": "dispatching",
                "title": event.title,
                "meeting_url": event.meeting_url,
                "starts_at": event.starts_at.isoformat(),
                "ends_at": event.ends_at.isoformat() if event.ends_at else None,
                "calendar_source": event.calendar_source,
                "initial_agenda_present": bool(extract_agenda_from_description(event.description)),
                "dynamic_agenda_status": "not_needed" if extract_agenda_from_description(event.description) else "watching",
                "last_attempt_at": attempt_at,
                "attempts": int(record.get("attempts") or 0) + 1,
                "error": None,
            }
            dispatched[event_id] = record
            write_json_file(self.dispatch_state_file, dispatch_state)

            try:
                result = await self.dispatch_event(event, event_id)
            except Exception as error:
                record.update(
                    {
                        "status": "failed",
                        "error": str(error),
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                print(f"[CalendarMonitor] Dispatch failed for {event_id}: {error}")
            else:
                record.update(
                    {
                        "status": "dispatched",
                        "dispatched_at": datetime.now(timezone.utc).isoformat(),
                        "result": result,
                        "node_id": result.get("node_id"),
                        "bot_id": result.get("bot_id"),
                        "task_id": result.get("task_id") or result.get("session_id"),
                    }
                )
                self._last_dispatched_at = datetime.now(timezone.utc).isoformat()
            changed = True

        if await self.update_dynamic_agendas(events, dispatched, now):
            changed = True

        if changed:
            write_json_file(self.dispatch_state_file, dispatch_state)
            refreshed_rows = []
            for event in relevant_events:
                event_id = self.external_event_id(event)
                refreshed_rows.append(self.event_to_row(event, event_id, dispatched.get(event_id), now))
            self.write_upcoming(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "range": {
                        "start": now.isoformat(),
                        "end": (now + timedelta(hours=self.lookahead_hours)).isoformat(),
                    },
                    "summary": self.upcoming_summary(refreshed_rows),
                    "events": refreshed_rows,
                }
            )

    async def update_dynamic_agendas(self, events: list[CalendarEvent], dispatched: dict, now: datetime) -> bool:
        if not self.dynamic_agenda_enabled:
            return False

        nodes_by_id = {node.id: node for node in load_nodes()}
        retained = set()
        changed = False
        for event in events:
            event_id = self.external_event_id(event)
            record = dispatched.get(event_id) or {}
            session_id = str(record.get("task_id") or (record.get("result") or {}).get("session_id") or "")
            node_id = str(record.get("node_id") or "")
            bot_id = str(record.get("bot_id") or "")
            key = (event_id, node_id, bot_id, session_id)
            if record.get("status") != "dispatched" or record.get("dynamic_agenda_done"):
                continue
            retained.add(key)
            if not self.should_poll_dynamic_agenda(event, record, now):
                continue
            record["dynamic_agenda_last_checked_at"] = datetime.now(timezone.utc).isoformat()
            node = nodes_by_id.get(node_id)
            changed = True
            if node is None or not bot_id or not session_id:
                record.update(dynamic_agenda_status="missing_assignment", dynamic_agenda_error=None)
                continue
            client = BotNodeClient(node, timeout_seconds=5)
            try:
                status = await asyncio.to_thread(client.agenda_status, bot_id)
            except BotNodeError as error:
                if error.status_code == 404:
                    record.update(dynamic_agenda_status="meeting_ended", dynamic_agenda_done=True)
                    retained.discard(key)
                else:
                    record.update(dynamic_agenda_status="status_error")
                record["dynamic_agenda_error"] = None
                continue
            if status.get("session_id") != session_id:
                record.update(dynamic_agenda_status="meeting_ended", dynamic_agenda_done=True,
                              dynamic_agenda_error=None)
                retained.discard(key)
                continue
            if status.get("agenda_active"):
                result = {"status": "already_active", "source": status.get("source"),
                          "items_count": status.get("items_count")}
            elif not status.get("meeting_started"):
                record.update(dynamic_agenda_status="waiting_for_meeting", dynamic_agenda_error=None)
                continue
            else:
                # This description was freshly fetched this cycle. Changed text replaces any
                # pending result before it can be sent; the session is guarded on the bot too.
                result = await self._calendar_agendas.step(
                    key, event.description, extract_agenda_from_description(event.description),
                    client, bot_id, session_id)
            result_status = result.get("status", "watching")
            done = result_status in ("agenda_activated", "already_active", "meeting_ended")
            record.update(dynamic_agenda_status=result_status, dynamic_agenda_done=done,
                          dynamic_agenda_error=None,
                          dynamic_agenda_source=result.get("source") or "calendar_monitor",
                          dynamic_agenda_items_count=result.get("items_count"))
            # No model response or absence/error message is published to a bot card or chat.
            record.pop("dynamic_agenda_result", None)
            if done:
                retained.discard(key)
                record["dynamic_agenda_stop_reason"] = result_status
        self._calendar_agendas.retain(retained)
        return changed

    def should_poll_dynamic_agenda(self, event: CalendarEvent, record: dict, now: datetime) -> bool:
        if record.get("status") != "dispatched":
            return False
        if record.get("dynamic_agenda_done"):
            return False
        if event.starts_at.astimezone(timezone.utc) > now:
            return False

        last_checked = parse_iso_datetime(record.get("dynamic_agenda_last_checked_at"))
        if last_checked is not None:
            elapsed = (now - last_checked.astimezone(timezone.utc)).total_seconds()
            if elapsed < self.dynamic_agenda_interval:
                return False
        return True

    @staticmethod
    def event_is_currently_active(event: CalendarEvent, now: datetime) -> bool:
        starts_at = event.starts_at.astimezone(timezone.utc)
        ends_at = event.ends_at.astimezone(timezone.utc) if event.ends_at else starts_at + timedelta(hours=1)
        return starts_at <= now <= ends_at

    def event_is_in_control_window(self, event: CalendarEvent, now: datetime) -> bool:
        starts_at = event.starts_at.astimezone(timezone.utc)
        lower_bound = now - self.missed_lookback
        upper_bound = now + timedelta(hours=self.lookahead_hours)
        return lower_bound <= starts_at <= upper_bound

    def should_dispatch_from_control(self, event: CalendarEvent, now: datetime) -> bool:
        starts_at = event.starts_at.astimezone(timezone.utc)
        ends_at = event.ends_at.astimezone(timezone.utc) if event.ends_at else starts_at + timedelta(hours=1)
        earliest = starts_at - self.join_before
        latest = starts_at + self.missed_lookback
        return earliest <= now <= latest and ends_at >= now

    def external_event_id(self, event: CalendarEvent) -> str:
        starts_at = event.starts_at.isoformat() if event.starts_at else "unknown-start"
        return f"calendar:{event.uid}:{starts_at}"

    def occurrence_key(self, event: CalendarEvent) -> str:
        starts_at = event.starts_at.astimezone(timezone.utc).isoformat()
        meeting_url = normalize_meeting_url(event.meeting_url)
        return f"{meeting_url}|{starts_at}" if meeting_url else f"{event.uid}|{starts_at}"

    def deduplicate_occurrences(self, events: list[CalendarEvent]) -> list[CalendarEvent]:
        unique: dict[str, CalendarEvent] = {}
        for event in events:
            key = self.occurrence_key(event)
            current = unique.get(key)
            if current is None:
                unique[key] = event
                continue
            current_agenda = bool(extract_agenda_from_description(current.description))
            candidate_agenda = bool(extract_agenda_from_description(event.description))
            if candidate_agenda and not current_agenda:
                unique[key] = event
            elif candidate_agenda == current_agenda and len(event.attendees) > len(current.attendees):
                unique[key] = event
        return list(unique.values())

    def event_to_row(self, event: CalendarEvent, event_id: str, record: dict | None, now: datetime) -> dict:
        record = record or {}
        starts_at = event.starts_at.astimezone(timezone.utc)
        if record.get("status"):
            status = record["status"]
        elif starts_at < now:
            status = "missed_candidate" if event.meeting_url else "past_no_link"
        elif starts_at <= now + self.join_before:
            status = "due"
        else:
            status = "upcoming"

        agenda = extract_agenda_from_description(event.description)
        return {
            "event_id": event_id,
            "title": event.title,
            "description": event.description,
            "agenda": agenda,
            "has_agenda": bool(agenda),
            "meeting_url": event.meeting_url,
            "starts_at": event.starts_at.isoformat(),
            "ends_at": event.ends_at.isoformat() if event.ends_at else None,
            "calendar_source": event.calendar_source,
            "status": status,
            "last_attempt_at": record.get("last_attempt_at"),
            "dispatched_at": record.get("dispatched_at"),
            "node_id": record.get("node_id"),
            "bot_id": record.get("bot_id"),
            "task_id": record.get("task_id"),
            "attempts": record.get("attempts", 0),
            "error": record.get("error"),
            **calendar_attendees_payload(event.attendees),
        }

    def upcoming_summary(self, rows: list[dict]) -> dict:
        return {
            "events_total": len(rows),
            "events_with_telemost": sum(1 for item in rows if item.get("meeting_url")),
            "due": sum(1 for item in rows if item.get("status") in ("due", "missed_candidate")),
            "dispatched": sum(1 for item in rows if item.get("status") == "dispatched"),
            "failed": sum(1 for item in rows if item.get("status") == "failed"),
        }

    def read_upcoming(self) -> dict:
        return read_json_file(self.upcoming_file, {"generated_at": None, "summary": {}, "events": []})

    def write_upcoming(self, payload: dict) -> None:
        write_json_file(self.upcoming_file, payload)

    def read_dispatch_state(self) -> dict:
        return read_json_file(self.dispatch_state_file, {"dispatched": {}})

    def fetch_ics(self, url: str) -> str:
        headers = {"Accept": "text/calendar"}
        auth_header = os.getenv("CALENDAR_AUTH_HEADER", "").strip()
        if auth_header:
            headers["Authorization"] = auth_header
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8-sig", errors="replace")

    async def fetch_events(self) -> list[CalendarEvent]:
        if self.provider == "caldav":
            return await asyncio.to_thread(self.fetch_caldav_events)

        events = []
        for index, url in enumerate(self.ics_urls(), start=1):
            text = await asyncio.to_thread(self.fetch_ics, url)
            events.extend(parse_ics_events(text, f"ics-{index}", self.timezone))
        return events

    def caldav_is_configured(self) -> bool:
        return bool(
            os.getenv("CALENDAR_CALDAV_URL", "").strip()
            and os.getenv("CALENDAR_USERNAME", "").strip()
            and os.getenv("CALENDAR_PASSWORD", "").strip()
        )

    def _caldav_client(self):
        import caldav

        return caldav.DAVClient(
            url=os.getenv("CALENDAR_CALDAV_URL", "https://caldav.yandex.ru/").strip(),
            username=os.getenv("CALENDAR_USERNAME", "").strip(),
            password=os.getenv("CALENDAR_PASSWORD", "").strip().strip('"'),
        )

    def list_caldav_calendars(self) -> list[dict]:
        if not self.caldav_is_configured():
            return []
        client = self._caldav_client()
        principal = client.principal()
        calendars = principal.calendars()
        result = []
        for calendar in calendars:
            result.append(
                {
                    "name": getattr(calendar, "name", None),
                    "url": str(getattr(calendar, "url", "")),
                }
            )
        return result

    def selected_caldav_calendars(self):
        client = self._caldav_client()
        principal = client.principal()
        calendars = principal.calendars()
        name_filter = os.getenv("CALENDAR_NAME", "").strip()
        if not name_filter:
            return calendars

        selected = []
        for calendar in calendars:
            name = str(getattr(calendar, "name", "") or "")
            url = str(getattr(calendar, "url", "") or "")
            if name == name_filter or name_filter in url:
                selected.append(calendar)
        return selected

    def all_caldav_calendars(self):
        client = self._caldav_client()
        principal = client.principal()
        return principal.calendars()

    def fetch_caldav_events(self) -> list[CalendarEvent]:
        calendars = self.selected_caldav_calendars()
        if not calendars:
            raise RuntimeError("No CalDAV calendars found")

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=max(24, self.dispatch_keep_hours))
        end = now + self.join_before + timedelta(hours=6)

        events: list[CalendarEvent] = []
        for index, calendar in enumerate(calendars, start=1):
            calendar_name = str(getattr(calendar, "name", None) or f"caldav-{index}")
            try:
                objects = calendar.search(start=start, end=end, event=True, expand=True)
            except TypeError:
                objects = calendar.date_search(start=start, end=end)

            for event_object in objects:
                data = getattr(event_object, "data", None)
                if not data:
                    try:
                        data = event_object.load().data
                    except Exception:
                        continue
                events.extend(parse_ics_events(data, calendar_name, self.timezone))
        return events

    def preview_company_events(self, days: int = 2) -> dict:
        if self.provider != "caldav":
            raise RuntimeError("Company calendar preview currently requires CALENDAR_PROVIDER=caldav")
        if not self.caldav_is_configured():
            raise RuntimeError("CalDAV is not configured")

        safe_days = max(1, min(int(days), 14))
        calendars = self.all_caldav_calendars()
        now = datetime.now(timezone.utc)
        start = now
        end = now + timedelta(days=safe_days)
        preview_events: list[dict] = []
        calendar_summaries: list[dict] = []

        for index, calendar in enumerate(calendars, start=1):
            calendar_name = str(getattr(calendar, "name", None) or f"caldav-{index}")
            calendar_url = str(getattr(calendar, "url", "") or "")
            try:
                try:
                    objects = calendar.search(start=start, end=end, event=True, expand=True)
                except TypeError:
                    objects = calendar.date_search(start=start, end=end)
            except Exception as error:
                calendar_summaries.append(
                    {
                        "name": calendar_name,
                        "url": calendar_url,
                        "status": "error",
                        "error": str(error),
                        "events_count": 0,
                    }
                )
                continue

            calendar_count = 0
            for event_object in objects:
                data = getattr(event_object, "data", None)
                if not data:
                    try:
                        data = event_object.load().data
                    except Exception:
                        continue
                events = [
                    event
                    for event in parse_ics_preview_events(data, calendar_name, self.timezone)
                    if preview_event_is_current_or_future(event, now)
                ]
                calendar_count += len(events)
                preview_events.extend(events)

            calendar_summaries.append(
                {
                    "name": calendar_name,
                    "url": calendar_url,
                    "status": "ok",
                    "error": None,
                    "events_count": calendar_count,
                }
            )

        preview_events.sort(key=lambda item: item.get("starts_at") or "")
        return {
            "mode": "preview",
            "days": safe_days,
            "checked_at": now.isoformat(),
            "range": {
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            "calendars": calendar_summaries,
            "summary": {
                "calendars_total": len(calendar_summaries),
                "events_total": len(preview_events),
                "events_with_telemost": sum(1 for item in preview_events if item.get("has_telemost_url")),
            },
            "events": preview_events,
        }

    def should_dispatch(self, event: CalendarEvent, now_utc: datetime) -> bool:
        starts_at = event.starts_at.astimezone(timezone.utc)
        ends_at = event.ends_at.astimezone(timezone.utc) if event.ends_at else starts_at + timedelta(hours=1)
        earliest_join = starts_at - self.join_before
        latest_join = starts_at + self.join_after_start
        return earliest_join <= now_utc <= latest_join and ends_at >= now_utc

    async def dispatch_event(self, event: CalendarEvent, external_event_id: str) -> dict:
        agenda = extract_agenda_from_description(event.description)
        payload = {
            "meeting_url": event.meeting_url,
            "title": event.title,
            "agenda": None if self.control_enabled and self.dynamic_agenda_enabled else (agenda or None),
            "source": "bot_calendar",
            "external_event_id": external_event_id,
            "scheduled_start_at": event.starts_at.isoformat(),
            "scheduled_end_at": event.ends_at.isoformat() if event.ends_at else None,
            "organizer": format_expected_participants((event.organizer_attendee,)) if event.organizer_attendee else None,
            "expected_participants": format_expected_participants(event.attendees) or None,
        }

        async with meeting_dispatch_lock:
            nodes = load_nodes()
            statuses = await asyncio.gather(*(asyncio.to_thread(BotNodeClient(node).status) for node in nodes))
            existing = active_assignment(statuses, event.meeting_url)
            if existing is not None:
                raise RuntimeError(f"Meeting is already assigned: {existing}")
            for node, status in zip(nodes, statuses):
                if status.get("status") != "online":
                    continue
                if int(status.get("bots_idle") or 0) <= 0:
                    continue
                try:
                    result = await asyncio.to_thread(BotNodeClient(node).create_meeting_any_bot, payload)
                    print(f"[CalendarMonitor] Dispatched {event.uid} to {node.id}: {result}")
                    return {"node_id": node.id, **result}
                except BotNodeError as error:
                    print(f"[CalendarMonitor] Dispatch to {node.id} failed: {error}")

        raise RuntimeError("No idle bot available for calendar event")


def unfold_ics_lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and result:
            result[-1] += line[1:]
        else:
            result.append(line)
    return result


def unescape_ics(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def extract_agenda_from_description(description: str) -> str:
    if not description:
        return ""
    match = AGENDA_BLOCK_RE.search(description)
    if not match:
        return ""
    agenda = match.group(1).strip()
    lines = [line.strip() for line in agenda.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    agenda = "\n".join(line for line in lines if line)
    return agenda


def parse_ics_params(left: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for part in left.split(";")[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        params[key.upper()] = value.strip().strip('"')
    return params



def attendee_to_dict(attendee: CalendarAttendee) -> dict:
    return {
        "name": attendee.name,
        "email": attendee.email,
        "partstat": attendee.partstat,
        "role": attendee.role,
    }


def parse_mailto(value: str) -> str | None:
    raw = (value or "").strip()
    if raw.lower().startswith("mailto:"):
        return raw[7:].strip() or None
    if "@" in raw and not raw.startswith(("http://", "https://")):
        return raw.strip() or None
    return None


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def attendee_excluded(attendee: CalendarAttendee) -> bool:
    email = normalize_email(attendee.email)
    name = attendee.name.strip().lower()
    username = normalize_email(os.getenv("CALENDAR_USERNAME", ""))
    excluded_emails = {
        normalize_email(item)
        for item in re.split(r"[,;\n]+", os.getenv("CALENDAR_ATTENDEE_EXCLUDE_EMAILS", ""))
        if item.strip()
    }
    if username:
        excluded_emails.add(username)
    if email and email in excluded_emails:
        return True
    if attendee.partstat and attendee.partstat.upper() == "DECLINED":
        return True

    resource_patterns = [
        item.strip().lower()
        for item in re.split(r"[,;\n]+", os.getenv("CALENDAR_ATTENDEE_EXCLUDE_PATTERNS", "conference_hall,переговор,зал"))
        if item.strip()
    ]
    haystack = f"{name} {email}"
    return any(pattern in haystack for pattern in resource_patterns)



def parse_ics_organizer(value: str | None, params: dict[str, str] | None) -> CalendarAttendee | None:
    if not value:
        return None
    params = params or {}
    email = parse_mailto(value)
    name = unescape_ics(params.get("CN", "") or "").strip()
    if not name:
        name = email or value.strip()
    organizer = CalendarAttendee(name=name, email=email, partstat="ACCEPTED", role="ORGANIZER")
    if attendee_excluded(organizer):
        return None
    return organizer


def merge_organizer_and_attendees(
    organizer: CalendarAttendee | None,
    attendees: tuple[CalendarAttendee, ...],
) -> tuple[CalendarAttendee, ...]:
    merged: list[CalendarAttendee] = []
    seen: set[tuple[str, str]] = set()
    for attendee in ([organizer] if organizer else []) + list(attendees):
        if attendee is None:
            continue
        key = (attendee.name.casefold(), normalize_email(attendee.email))
        if key in seen:
            continue
        seen.add(key)
        merged.append(attendee)
    return tuple(merged)


def parse_ics_attendees(raw_attendees: list[tuple[str, dict[str, str]]]) -> tuple[CalendarAttendee, ...]:
    attendees: list[CalendarAttendee] = []
    seen: set[tuple[str, str]] = set()
    for value, params in raw_attendees:
        email = parse_mailto(value)
        name = unescape_ics(params.get("CN", "") or "").strip()
        if not name:
            name = email or value.strip()
        attendee = CalendarAttendee(
            name=name,
            email=email,
            partstat=(params.get("PARTSTAT") or None),
            role=(params.get("ROLE") or None),
        )
        if attendee_excluded(attendee):
            continue
        key = (attendee.name.casefold(), normalize_email(attendee.email))
        if key in seen:
            continue
        seen.add(key)
        attendees.append(attendee)
    return tuple(attendees)


def format_expected_participants(attendees: tuple[CalendarAttendee, ...]) -> str:
    lines = []
    for attendee in attendees:
        name = attendee.name.strip()
        email = (attendee.email or "").strip()
        if not name:
            continue
        lines.append(f"{name} - {email}" if email else name)
    return "\n".join(lines)


def attendee_role_group(attendee: CalendarAttendee) -> str:
    role = (attendee.role or "").upper()
    if role == "OPT-PARTICIPANT":
        return "optional"
    return "required"


def split_attendees_by_role(attendees: tuple[CalendarAttendee, ...]) -> tuple[tuple[CalendarAttendee, ...], tuple[CalendarAttendee, ...]]:
    required = []
    optional = []
    for attendee in attendees:
        if attendee_role_group(attendee) == "optional":
            optional.append(attendee)
        else:
            required.append(attendee)
    return tuple(required), tuple(optional)


def calendar_attendees_payload(attendees: tuple[CalendarAttendee, ...]) -> dict:
    required, optional = split_attendees_by_role(attendees)
    return {
        "attendees_count": len(attendees),
        "attendees_required_count": len(required),
        "attendees_optional_count": len(optional),
        "attendees": [attendee_to_dict(item) for item in attendees],
        "required_attendees": [attendee_to_dict(item) for item in required],
        "optional_attendees": [attendee_to_dict(item) for item in optional],
        "expected_participants": format_expected_participants(attendees),
        "expected_required_participants": format_expected_participants(required),
        "expected_optional_participants": format_expected_participants(optional),
    }


def timezone_from_tzid(tzid: str | None, default_tz):
    if not tzid:
        return default_tz
    try:
        return ZoneInfo(tzid)
    except ZoneInfoNotFoundError:
        print(f"[CalendarMonitor] Unknown TZID {tzid!r}; using default calendar timezone")
        return default_tz


def parse_ics_datetime(raw: str, default_tz, params: dict[str, str] | None = None) -> datetime:
    value = raw.strip()
    params = params or {}
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)

    tz = timezone_from_tzid(params.get("TZID"), default_tz)
    if "T" in value:
        fmt = "%Y%m%dT%H%M%S" if len(value) >= 15 else "%Y%m%dT%H%M"
        return datetime.strptime(value, fmt).replace(tzinfo=tz)

    parsed_date = datetime.strptime(value, "%Y%m%d").date()
    return datetime.combine(parsed_date, time.min, tzinfo=tz)


def extract_prop(line: str) -> tuple[str, str, dict[str, str]] | None:
    if ":" not in line:
        return None
    left, value = line.split(":", 1)
    name = left.split(";", 1)[0].upper()
    return name, unescape_ics(value), parse_ics_params(left)


def extract_telemost_url(*values: str) -> str | None:
    text = "\n".join(value or "" for value in values)
    match = TELEMOST_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(").,;]")


def extract_telemost_url_with_source(fields: dict[str, str]) -> tuple[str | None, str | None]:
    for name in ("SUMMARY", "DESCRIPTION", "LOCATION", "URL"):
        value = fields.get(name, "")
        match = TELEMOST_RE.search(value or "")
        if match:
            return match.group(0).rstrip(").,;]"), name.lower()
    return None, None


def parse_ics_events(text: str, source_name: str, default_tz) -> list[CalendarEvent]:
    events = []
    current: dict[str, str] | None = None
    current_params: dict[str, dict[str, str]] = {}
    current_attendees: list[tuple[str, dict[str, str]]] = []
    current_organizer: tuple[str, dict[str, str]] | None = None
    for line in unfold_ics_lines(text):
        if line == "BEGIN:VEVENT":
            current = {}
            current_params = {}
            current_attendees = []
            current_organizer = None
            continue
        if line == "END:VEVENT" and current is not None:
            try:
                meeting_url = extract_telemost_url(
                    current.get("SUMMARY", ""),
                    current.get("DESCRIPTION", ""),
                    current.get("LOCATION", ""),
                )
                if meeting_url and current.get("DTSTART"):
                    starts_at = parse_ics_datetime(current["DTSTART"], default_tz, current_params.get("DTSTART"))
                    ends_at = parse_ics_datetime(current["DTEND"], default_tz, current_params.get("DTEND")) if current.get("DTEND") else None
                    uid = current.get("UID") or f"{source_name}:{current.get('DTSTART')}:{meeting_url}"
                    title = current.get("SUMMARY") or uid
                    events.append(
                        CalendarEvent(
                            uid=uid,
                            title=title,
                            description=current.get("DESCRIPTION", ""),
                            location=current.get("LOCATION", ""),
                            starts_at=starts_at,
                            ends_at=ends_at,
                            meeting_url=meeting_url,
                            calendar_source=source_name,
                            attendees=merge_organizer_and_attendees(
                                parse_ics_organizer(*current_organizer) if current_organizer else None,
                                parse_ics_attendees(current_attendees),
                            ),
                            organizer_attendee=parse_ics_organizer(*current_organizer) if current_organizer else None,
                        )
                    )
            finally:
                current = None
            continue
        if current is not None:
            prop = extract_prop(line)
            if prop:
                name, value, params = prop
                if name == "ATTENDEE":
                    current_attendees.append((value, params))
                    continue
                if name == "ORGANIZER":
                    current_organizer = (value, params)
                current[name] = value
                current_params[name] = params
    return events


def parse_ics_preview_events(text: str, source_name: str, default_tz) -> list[dict]:
    events = []
    current: dict[str, str] | None = None
    current_params: dict[str, dict[str, str]] = {}
    current_attendees: list[tuple[str, dict[str, str]]] = []
    current_organizer: tuple[str, dict[str, str]] | None = None
    for line in unfold_ics_lines(text):
        if line == "BEGIN:VEVENT":
            current = {}
            current_params = {}
            current_attendees = []
            current_organizer = None
            continue
        if line == "END:VEVENT" and current is not None:
            try:
                if current.get("DTSTART"):
                    starts_at = parse_ics_datetime(current["DTSTART"], default_tz, current_params.get("DTSTART"))
                    ends_at = parse_ics_datetime(current["DTEND"], default_tz, current_params.get("DTEND")) if current.get("DTEND") else None
                    uid = current.get("UID") or f"{source_name}:{current.get('DTSTART')}:{current.get('SUMMARY', '')}"
                    title = current.get("SUMMARY") or uid
                    meeting_url, url_source = extract_telemost_url_with_source(current)
                    organizer_attendee = parse_ics_organizer(*current_organizer) if current_organizer else None
                    attendees = merge_organizer_and_attendees(
                        organizer_attendee,
                        parse_ics_attendees(current_attendees),
                    )
                    events.append(
                        {
                            "uid": uid,
                            "title": title,
                            "description": current.get("DESCRIPTION", ""),
                            "agenda": extract_agenda_from_description(current.get("DESCRIPTION", "")),
                            "has_agenda": bool(extract_agenda_from_description(current.get("DESCRIPTION", ""))),
                            "location": current.get("LOCATION", ""),
                            "organizer": attendee_to_dict(organizer_attendee) if organizer_attendee else None,
                            "organizer_raw": current.get("ORGANIZER", ""),
                            "starts_at": starts_at.isoformat(),
                            "ends_at": ends_at.isoformat() if ends_at else None,
                            "calendar_source": source_name,
                            "meeting_url": meeting_url,
                            "has_telemost_url": meeting_url is not None,
                            "telemost_url_source": url_source,
                            "will_dispatch": False,
                            "reason": "preview_only" if meeting_url else "telemost_url_not_found",
                            **calendar_attendees_payload(attendees),
                        }
                    )
            finally:
                current = None
            continue
        if current is not None:
            prop = extract_prop(line)
            if prop:
                name, value, params = prop
                if name == "ATTENDEE":
                    current_attendees.append((value, params))
                    continue
                if name == "ORGANIZER":
                    current_organizer = (value, params)
                current[name] = value
                current_params[name] = params
    return events


def preview_event_is_current_or_future(event: dict, now_utc: datetime) -> bool:
    starts_at = parse_iso_datetime(event.get("starts_at"))
    if starts_at is not None:
        return starts_at.astimezone(timezone.utc) >= now_utc
    return False


def parse_iso_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


calendar_monitor = CalendarMonitor()
