from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .bot_node_client import BotNodeClient
from .config import BotNodeConfig, PROJECT_ROOT


LOGGER = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
CALENDAR_EVENT_RE = re.compile(r"^calendar:(.+):(\d{4}-\d{2}-\d{2}T.+)$")
AGENDA_ITEM_RE = re.compile(r"(?m)^\s*#\s*\d+\s*[.)-]?\s+\S")


class Base(DeclarativeBase):
    pass


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurrence_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    recurrence_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    organizer_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    organizer_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    actual_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    actual_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    actual_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    telemost_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    agenda_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    agenda_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agenda_items_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    bot_participated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bot_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    node_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    processing_status: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    disk_folder_exists: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, index=True
    )
    disk_empty_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unknown", index=True
    )
    disk_folder_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    disk_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disk_scan_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    empty_marker_found: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disk_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    disk_artifacts_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="pending", index=True
    )
    disk_artifacts_found: Mapped[str | None] = mapped_column(Text, nullable=True)
    disk_artifacts_missing: Mapped[str | None] = mapped_column(Text, nullable=True)
    disk_artifacts_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disk_artifacts_finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Astrakhan")


def _parse_datetime(value: Any, timezone: ZoneInfo) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _sqlite_datetime(value: datetime | None, timezone: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    # SQLite does not preserve the offset in DateTime columns. All values are
    # deliberately normalized to the single business timezone before storage.
    return value.astimezone(timezone).replace(tzinfo=None)


def _api_datetime(value: datetime | None, timezone: ZoneInfo) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone)
    return value.astimezone(timezone).isoformat()


def _organizer(value: Any) -> tuple[str | None, str | None]:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None, None
    match = EMAIL_RE.search(text)
    email = match.group(0).lower() if match else None
    if email:
        name = text[: match.start()].strip(" <>-–—,;") or None
    else:
        name = text
    return name, email


def _event_identity(metadata: dict[str, Any], task: dict[str, Any], node_id: str) -> tuple[str, str, str | None]:
    external_event_id = str(metadata.get("external_event_id") or "").strip()
    if external_event_id:
        calendar_match = CALENDAR_EVENT_RE.match(external_event_id)
        if calendar_match:
            event_id = calendar_match.group(1)
            recurrence_id = calendar_match.group(2)
        else:
            event_id = external_event_id
            recurrence_id = str(metadata.get("scheduled_start_at") or "").strip() or None
        return external_event_id, event_id, recurrence_id

    task_id = str(task.get("task_id") or "unknown")
    created_at = str(task.get("created_at") or "unknown")
    occurrence_key = f"manual:{node_id}:{task_id}:{created_at}"
    return occurrence_key, task_id, str(metadata.get("scheduled_start_at") or "").strip() or None


def _agenda(record: dict[str, Any], metadata: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str | None, int]:
    raw_agenda = str(result.get("agenda") or metadata.get("agenda") or "").strip()
    recorded_count = record.get("dynamic_agenda_items_count")
    try:
        item_count = max(0, int(recorded_count)) if recorded_count is not None else 0
    except (TypeError, ValueError):
        item_count = 0
    if item_count == 0 and raw_agenda:
        item_count = len(AGENDA_ITEM_RE.findall(raw_agenda))

    raw_source = str(record.get("dynamic_agenda_source") or "").strip().lower()
    if not raw_source and item_count > 0 and raw_agenda:
        task_source = str(result.get("source") or metadata.get("source") or "").strip().lower()
        if task_source in {"control_service", "control_dashboard", "dashboard"}:
            raw_source = "dashboard"
        elif task_source in {"bot_calendar", "calendar_monitor", "calendar"}:
            raw_source = "calendar"
    aliases = {
        "calendar_monitor": "calendar",
        "bot_calendar": "calendar",
        "initial": "calendar",
        "chat_command": "chat",
        "chat": "chat",
        "control_dashboard": "dashboard",
        "dashboard": "dashboard",
    }
    source = aliases.get(raw_source, raw_source or None)
    return item_count > 0, source if item_count > 0 else None, item_count


class MeetingRepository:
    def __init__(self, database_url: str, timezone_name: str = "Europe/Astrakhan") -> None:
        self.timezone = _timezone(timezone_name)
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, future=True, connect_args=connect_args)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, class_=Session)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        if self.engine.dialect.name != "sqlite":
            return
        with self.engine.connect() as connection:
            existing_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(meetings)")
            }
        additions = {
            "disk_folder_exists": "BOOLEAN",
            "disk_empty_status": "VARCHAR(40) NOT NULL DEFAULT 'unknown'",
            "disk_folder_path": "VARCHAR(2000)",
            "disk_checked_at": "DATETIME",
            "disk_scan_completed": "BOOLEAN NOT NULL DEFAULT 0",
            "empty_marker_found": "BOOLEAN NOT NULL DEFAULT 0",
            "disk_error": "VARCHAR(2000)",
            "disk_artifacts_status": "VARCHAR(40) NOT NULL DEFAULT 'pending'",
            "disk_artifacts_found": "TEXT",
            "disk_artifacts_missing": "TEXT",
            "disk_artifacts_checked_at": "DATETIME",
            "disk_artifacts_finalized_at": "DATETIME",
        }
        with self.engine.begin() as connection:
            for column_name, definition in additions.items():
                if column_name not in existing_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE meetings ADD COLUMN {column_name} {definition}"
                    )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_meetings_disk_folder_exists "
                "ON meetings (disk_folder_exists)"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_meetings_disk_empty_status "
                "ON meetings (disk_empty_status)"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_meetings_disk_artifacts_status "
                "ON meetings (disk_artifacts_status)"
            )
            connection.exec_driver_sql(
                "UPDATE meetings SET disk_folder_exists = CASE "
                "WHEN disk_folder_path IS NOT NULL AND disk_folder_path != '' THEN 1 "
                "WHEN disk_checked_at IS NOT NULL THEN 0 "
                "ELSE NULL END "
                "WHERE disk_folder_exists IS NULL"
            )
            connection.exec_driver_sql(
                "UPDATE meetings SET disk_artifacts_status = CASE "
                "WHEN disk_empty_status = 'empty' AND disk_folder_path IS NOT NULL THEN 'empty_confirmed' "
                "WHEN disk_empty_status = 'not_empty' AND disk_folder_path IS NOT NULL THEN 'complete' "
                "WHEN disk_empty_status = 'folder_not_found' THEN 'folder_missing' "
                "WHEN disk_empty_status = 'scan_missed' THEN 'scan_missed' "
                "ELSE disk_artifacts_status END "
                "WHERE disk_scan_completed = 1 AND disk_artifacts_status IN ('pending', 'unknown')"
            )
            connection.exec_driver_sql(
                "UPDATE meetings SET "
                "disk_artifacts_missing = '[\"папка встречи на Яндекс Диске\"]', "
                "disk_artifacts_checked_at = COALESCE(disk_artifacts_checked_at, disk_checked_at), "
                "disk_artifacts_finalized_at = COALESCE(disk_artifacts_finalized_at, disk_checked_at) "
                "WHERE disk_artifacts_status IN ('folder_missing', 'scan_missed') "
                "AND (disk_artifacts_missing IS NULL OR disk_artifacts_missing = '')"
            )

    def upsert_completed_task(
        self,
        *,
        node_id: str,
        task: dict[str, Any],
        dispatch_record: dict[str, Any] | None = None,
    ) -> str | None:
        if str(task.get("status") or "").lower() != "completed":
            return None
        result = task.get("result") if isinstance(task.get("result"), dict) else {}
        metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
        actual_start = _parse_datetime(result.get("meeting_started_at"), self.timezone)
        actual_end = _parse_datetime(result.get("meeting_ended_at"), self.timezone)
        if actual_start is None or actual_end is None or actual_end < actual_start:
            return None

        occurrence_key, event_id, recurrence_id = _event_identity(metadata, task, node_id)
        organizer_name, organizer_email = _organizer(result.get("organizer") or metadata.get("organizer"))
        agenda_present, agenda_source, agenda_items_count = _agenda(
            dispatch_record or {}, metadata, result
        )
        scheduled_start = _parse_datetime(metadata.get("scheduled_start_at"), self.timezone)
        scheduled_end = _parse_datetime(metadata.get("scheduled_end_at"), self.timezone)
        duration_seconds = max(0, int((actual_end - actual_start).total_seconds()))
        now = datetime.now(self.timezone)

        values = {
            "event_id": event_id,
            "recurrence_id": recurrence_id,
            "meeting_date": actual_start.date(),
            "title": str(metadata.get("title") or result.get("title") or "Без названия")[:1000],
            "organizer_email": organizer_email,
            "organizer_name": organizer_name,
            "scheduled_start_at": _sqlite_datetime(scheduled_start, self.timezone),
            "scheduled_end_at": _sqlite_datetime(scheduled_end, self.timezone),
            # Planned duration is intentionally not calculated or used.
            "scheduled_duration_seconds": None,
            "actual_start_at": _sqlite_datetime(actual_start, self.timezone),
            "actual_end_at": _sqlite_datetime(actual_end, self.timezone),
            "actual_duration_seconds": duration_seconds,
            "telemost_url": str(metadata.get("meeting_url") or "") or None,
            "agenda_present": agenda_present,
            "agenda_source": agenda_source,
            "agenda_items_count": agenda_items_count,
            "bot_participated": True,
            "bot_id": str(metadata.get("bot_id") or "") or None,
            "node_id": str(metadata.get("node_id") or node_id) or None,
            "processing_status": "bot_completed",
            "updated_at": _sqlite_datetime(now, self.timezone),
        }

        with self.session_factory() as session:
            meeting = session.scalar(select(Meeting).where(Meeting.occurrence_key == occurrence_key))
            if meeting is None:
                meeting = Meeting(
                    occurrence_key=occurrence_key,
                    created_at=_sqlite_datetime(now, self.timezone),
                    disk_empty_status="unknown",
                    disk_folder_exists=None,
                    disk_scan_completed=False,
                    empty_marker_found=False,
                    disk_artifacts_status="pending",
                    **values,
                )
                session.add(meeting)
                inserted = True
            else:
                for key, value in values.items():
                    setattr(meeting, key, value)
                inserted = False
            session.commit()
        return "inserted" if inserted else "updated"

    def summary(self, date_from: date | None = None, date_to: date | None = None) -> dict[str, Any]:
        filters = []
        if date_from:
            filters.append(Meeting.meeting_date >= date_from)
        if date_to:
            filters.append(Meeting.meeting_date <= date_to)
        with self.session_factory() as session:
            total, average_duration, agenda_count, empty_count, disk_checked_count = session.execute(
                select(
                    func.count(Meeting.id),
                    func.avg(Meeting.actual_duration_seconds),
                    func.sum(func.cast(Meeting.agenda_present, Integer)),
                    func.sum(
                        func.cast(Meeting.disk_empty_status == "empty", Integer)
                    ),
                    func.sum(
                        func.cast(
                            Meeting.disk_empty_status.in_(("empty", "not_empty")),
                            Integer,
                        )
                    ),
                ).where(*filters)
            ).one()
            organizer_rows = session.execute(
                select(
                    Meeting.organizer_name,
                    Meeting.organizer_email,
                    func.count(Meeting.id).label("meetings_count"),
                )
                .where(*filters)
                .where((Meeting.organizer_email.is_not(None)) | (Meeting.organizer_name.is_not(None)))
                .group_by(Meeting.organizer_name, Meeting.organizer_email)
                .order_by(func.count(Meeting.id).desc(), Meeting.organizer_name)
                .limit(10)
            ).all()
            artifact_rows = session.execute(
                select(Meeting.disk_artifacts_status, func.count(Meeting.id))
                .where(*filters)
                .group_by(Meeting.disk_artifacts_status)
            ).all()
        total = int(total or 0)
        agenda_count = int(agenda_count or 0)
        empty_count = int(empty_count or 0)
        disk_checked_count = int(disk_checked_count or 0)
        artifact_counts = {str(status or "pending"): int(count or 0) for status, count in artifact_rows}
        artifact_complete = sum(artifact_counts.get(status, 0) for status in ("complete", "empty_confirmed"))
        artifact_problem = sum(
            artifact_counts.get(status, 0)
            for status in ("partial", "folder_missing", "scan_missed", "error")
        )
        artifact_finalized = artifact_complete + artifact_problem
        return {
            "total_meetings": total,
            "average_actual_duration_seconds": int(average_duration or 0),
            "agenda_meetings": agenda_count,
            "without_agenda_meetings": max(0, total - agenda_count),
            "agenda_percentage": round((agenda_count / total * 100), 1) if total else 0.0,
            "empty_meetings": empty_count,
            "nonempty_meetings": max(0, disk_checked_count - empty_count),
            "disk_checked_meetings": disk_checked_count,
            "empty_percentage": (
                round((empty_count / disk_checked_count * 100), 1)
                if disk_checked_count
                else 0.0
            ),
            "artifact_complete_meetings": artifact_complete,
            "artifact_problem_meetings": artifact_problem,
            "artifact_pending_meetings": sum(
                artifact_counts.get(status, 0) for status in ("pending", "unknown")
            ),
            "artifact_success_percentage": (
                round(artifact_complete / artifact_finalized * 100, 1)
                if artifact_finalized
                else 0.0
            ),
            "artifact_status_counts": artifact_counts,
            "top_organizers": [
                {
                    "organizer_name": row.organizer_name,
                    "organizer_email": row.organizer_email,
                    "meetings_count": int(row.meetings_count),
                }
                for row in organizer_rows
            ],
        }

    def daily_empty_stats(
        self,
        *,
        days: int = 30,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        days = max(2, min(int(days), 366))
        end_date = end_date or datetime.now(self.timezone).date()
        start_date = end_date - timedelta(days=days - 1)
        with self.session_factory() as session:
            rows = session.execute(
                select(
                    Meeting.meeting_date,
                    Meeting.disk_empty_status,
                    func.count(Meeting.id),
                )
                .where(Meeting.meeting_date >= start_date)
                .where(Meeting.meeting_date <= end_date)
                .where(Meeting.disk_empty_status.in_(("empty", "not_empty")))
                .group_by(Meeting.meeting_date, Meeting.disk_empty_status)
            ).all()

        counts: dict[date, dict[str, int]] = {}
        for meeting_date, status, count in rows:
            day_counts = counts.setdefault(meeting_date, {"empty": 0, "not_empty": 0})
            day_counts[str(status)] = int(count or 0)

        daily: list[dict[str, Any]] = []
        for offset in range(days):
            current_date = start_date + timedelta(days=offset)
            day_counts = counts.get(current_date, {"empty": 0, "not_empty": 0})
            empty_count = int(day_counts["empty"])
            nonempty_count = int(day_counts["not_empty"])
            checked_count = empty_count + nonempty_count
            daily.append(
                {
                    "meeting_date": current_date.isoformat(),
                    "checked_meetings": checked_count,
                    "empty_meetings": empty_count,
                    "nonempty_meetings": nonempty_count,
                    "empty_percentage": (
                        round(empty_count / checked_count * 100, 1)
                        if checked_count
                        else None
                    ),
                }
            )

        def average_for_window(window_days: int) -> tuple[float | None, int]:
            percentages = [
                float(item["empty_percentage"])
                for item in daily[-window_days:]
                if item["empty_percentage"] is not None
            ]
            if not percentages:
                return None, 0
            return round(sum(percentages) / len(percentages), 1), len(percentages)

        current = daily[-1]
        previous = daily[-2]
        current_percentage = current["empty_percentage"]
        previous_percentage = previous["empty_percentage"]
        change = (
            round(float(current_percentage) - float(previous_percentage), 1)
            if current_percentage is not None and previous_percentage is not None
            else None
        )
        average_7, days_with_data_7 = average_for_window(7)
        average_30, days_with_data_30 = average_for_window(30)
        return {
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "current_day": current,
            "previous_day": previous,
            "change_from_previous_day_percentage_points": change,
            "average_daily_empty_percentage_7_days": average_7,
            "days_with_data_7_days": days_with_data_7,
            "average_daily_empty_percentage_30_days": average_30,
            "days_with_data_30_days": days_with_data_30,
            "daily": daily,
        }

    def list_meetings(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        organizer: str | None = None,
        agenda_present: bool | None = None,
        node_id: str | None = None,
        bot_id: str | None = None,
        disk_empty_status: str | None = None,
        disk_folder_exists: bool | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        statement = select(Meeting)
        if date_from:
            statement = statement.where(Meeting.meeting_date >= date_from)
        if date_to:
            statement = statement.where(Meeting.meeting_date <= date_to)
        if organizer:
            pattern = f"%{organizer.strip()}%"
            statement = statement.where(
                Meeting.organizer_name.ilike(pattern) | Meeting.organizer_email.ilike(pattern)
            )
        if agenda_present is not None:
            statement = statement.where(Meeting.agenda_present == agenda_present)
        if node_id:
            statement = statement.where(Meeting.node_id == node_id)
        if bot_id:
            statement = statement.where(Meeting.bot_id == bot_id)
        if disk_empty_status:
            statement = statement.where(Meeting.disk_empty_status == disk_empty_status)
        if disk_folder_exists is not None:
            statement = statement.where(Meeting.disk_folder_exists == disk_folder_exists)
        statement = statement.order_by(Meeting.actual_start_at.desc()).limit(max(1, min(limit, 2000)))
        with self.session_factory() as session:
            meetings = list(session.scalars(statement))
        return [self._serialize(meeting) for meeting in meetings]

    def _serialize(self, meeting: Meeting) -> dict[str, Any]:
        return {
            "id": meeting.id,
            "occurrence_key": meeting.occurrence_key,
            "event_id": meeting.event_id,
            "recurrence_id": meeting.recurrence_id,
            "meeting_date": meeting.meeting_date.isoformat(),
            "title": meeting.title,
            "organizer_email": meeting.organizer_email,
            "organizer_name": meeting.organizer_name,
            "scheduled_start_at": _api_datetime(meeting.scheduled_start_at, self.timezone),
            "scheduled_end_at": _api_datetime(meeting.scheduled_end_at, self.timezone),
            "scheduled_duration_seconds": meeting.scheduled_duration_seconds,
            "actual_start_at": _api_datetime(meeting.actual_start_at, self.timezone),
            "actual_end_at": _api_datetime(meeting.actual_end_at, self.timezone),
            "actual_duration_seconds": meeting.actual_duration_seconds,
            "telemost_url": meeting.telemost_url,
            "agenda_present": meeting.agenda_present,
            "agenda_source": meeting.agenda_source,
            "agenda_items_count": meeting.agenda_items_count,
            "bot_participated": meeting.bot_participated,
            "bot_id": meeting.bot_id,
            "node_id": meeting.node_id,
            "processing_status": meeting.processing_status,
            "disk_folder_exists": meeting.disk_folder_exists,
            "disk_empty_status": meeting.disk_empty_status,
            "disk_folder_path": meeting.disk_folder_path,
            "disk_checked_at": _api_datetime(meeting.disk_checked_at, self.timezone),
            "disk_scan_completed": meeting.disk_scan_completed,
            "empty_marker_found": meeting.empty_marker_found,
            "disk_error": meeting.disk_error,
            "disk_artifacts_status": meeting.disk_artifacts_status,
            "disk_artifacts_found": json.loads(meeting.disk_artifacts_found or "[]"),
            "disk_artifacts_missing": json.loads(meeting.disk_artifacts_missing or "[]"),
            "disk_artifacts_checked_at": _api_datetime(meeting.disk_artifacts_checked_at, self.timezone),
            "disk_artifacts_finalized_at": _api_datetime(meeting.disk_artifacts_finalized_at, self.timezone),
            "created_at": _api_datetime(meeting.created_at, self.timezone),
            "updated_at": _api_datetime(meeting.updated_at, self.timezone),
        }

    def disk_candidates(self, meeting_date: date, *, include_checked: bool = False) -> list[dict[str, Any]]:
        statement = select(Meeting).where(Meeting.meeting_date == meeting_date)
        if not include_checked:
            statement = statement.where(Meeting.disk_scan_completed.is_(False))
        statement = statement.order_by(Meeting.actual_start_at)
        with self.session_factory() as session:
            meetings = list(session.scalars(statement))
        return [self._serialize(meeting) for meeting in meetings]

    def update_disk_result(
        self,
        *,
        meeting_id: int,
        status: str,
        folder_path: str | None,
        marker_found: bool,
        completed: bool,
        folder_exists: bool | None = None,
        error: str | None = None,
        artifact_status: str | None = None,
        artifacts_found: list[str] | None = None,
        artifacts_missing: list[str] | None = None,
    ) -> bool:
        now = _sqlite_datetime(datetime.now(self.timezone), self.timezone)
        with self.session_factory() as session:
            meeting = session.get(Meeting, meeting_id)
            if meeting is None:
                return False
            meeting.disk_empty_status = status
            if folder_exists is True:
                meeting.disk_folder_exists = True
                meeting.disk_folder_path = folder_path
            elif folder_exists is False:
                meeting.disk_folder_exists = False
                meeting.disk_folder_path = None
            elif folder_path is not None:
                meeting.disk_folder_exists = True
                meeting.disk_folder_path = folder_path
            meeting.empty_marker_found = marker_found
            meeting.disk_scan_completed = completed
            meeting.disk_checked_at = now
            meeting.disk_error = error[:2000] if error else None
            if artifact_status:
                meeting.disk_artifacts_status = artifact_status
            if artifacts_found is not None:
                meeting.disk_artifacts_found = json.dumps(artifacts_found, ensure_ascii=False)
            if artifacts_missing is not None:
                meeting.disk_artifacts_missing = json.dumps(artifacts_missing, ensure_ascii=False)
            meeting.disk_artifacts_checked_at = now
            if completed or artifact_status in {"complete", "empty_confirmed", "folder_missing", "scan_missed"}:
                meeting.disk_artifacts_finalized_at = now
            meeting.updated_at = now
            session.commit()
        return True

    def artifact_problems(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        statement = select(Meeting).where(
            Meeting.disk_artifacts_status.in_(("partial", "folder_missing", "scan_missed", "error"))
        )
        if date_from:
            statement = statement.where(Meeting.meeting_date >= date_from)
        if date_to:
            statement = statement.where(Meeting.meeting_date <= date_to)
        statement = statement.order_by(Meeting.actual_end_at.desc()).limit(max(1, min(limit, 2000)))
        with self.session_factory() as session:
            meetings = list(session.scalars(statement))
        return [self._serialize(meeting) for meeting in meetings]


class MeetingAnalyticsCollector:
    def __init__(
        self,
        repository: MeetingRepository,
        nodes_provider: Callable[[], list[BotNodeConfig]],
        dispatch_state_provider: Callable[[], dict[str, Any]],
    ) -> None:
        self.repository = repository
        self.nodes_provider = nodes_provider
        self.dispatch_state_provider = dispatch_state_provider
        self.interval_seconds = max(5, int(os.getenv("ANALYTICS_POLL_INTERVAL_SECONDS", "30")))
        self.last_run: dict[str, Any] = {
            "status": "not_started",
            "started_at": None,
            "finished_at": None,
            "nodes": 0,
            "tasks_seen": 0,
            "completed_seen": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.collect_once()
            except Exception:
                LOGGER.exception("Meeting analytics collection failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop_event.set()

    async def collect_once(self) -> dict[str, Any]:
        async with self._lock:
            started = datetime.now(self.repository.timezone)
            nodes = self.nodes_provider()
            dispatch_state = self.dispatch_state_provider() or {}
            dispatch_records = dispatch_state.get("dispatched") or {}
            by_external_id = {
                str(record.get("event_id") or key): record
                for key, record in dispatch_records.items()
                if isinstance(record, dict)
            }
            results = await asyncio.gather(
                *(asyncio.to_thread(BotNodeClient(node).list_meeting_tasks) for node in nodes),
                return_exceptions=True,
            )
            run = {
                "status": "completed",
                "started_at": started.isoformat(),
                "finished_at": None,
                "nodes": len(nodes),
                "tasks_seen": 0,
                "completed_seen": 0,
                "inserted": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [],
            }
            for node, payload in zip(nodes, results):
                if isinstance(payload, Exception):
                    run["errors"].append({"node_id": node.id, "error": str(payload)})
                    continue
                tasks = payload.get("tasks") if isinstance(payload, dict) else []
                for task in tasks or []:
                    if not isinstance(task, dict):
                        continue
                    run["tasks_seen"] += 1
                    if str(task.get("status") or "").lower() != "completed":
                        continue
                    run["completed_seen"] += 1
                    metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
                    external_event_id = str(metadata.get("external_event_id") or "")
                    outcome = await asyncio.to_thread(
                        self.repository.upsert_completed_task,
                        node_id=node.id,
                        task=task,
                        dispatch_record=by_external_id.get(external_event_id),
                    )
                    if outcome is None:
                        run["skipped"] += 1
                    else:
                        run[outcome] += 1
            finished = datetime.now(self.repository.timezone)
            run["finished_at"] = finished.isoformat()
            if run["errors"]:
                run["status"] = "completed_with_errors"
            self.last_run = run
            return run


def database_url_from_env() -> str:
    return os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(PROJECT_ROOT / 'data' / 'meeting_analytics.sqlite3').as_posix()}",
    )


def app_timezone_from_env() -> str:
    return os.getenv("APP_TIMEZONE", "Europe/Astrakhan").strip() or "Europe/Astrakhan"
