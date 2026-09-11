from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from pathlib import Path

from control_service.analytics import MeetingRepository
from control_service.disk_analytics import MeetingDiskAnalyticsScanner, YandexDiskReader


class MeetingRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "analytics.sqlite3"
        self.repository = MeetingRepository(f"sqlite:///{database_path.as_posix()}")
        self.repository.initialize()

    def tearDown(self) -> None:
        self.repository.engine.dispose()
        self.temp_dir.cleanup()

    @staticmethod
    def completed_task() -> dict:
        return {
            "task_id": "task-1",
            "status": "completed",
            "created_at": "2026-08-20T05:30:00+00:00",
            "metadata": {
                "external_event_id": "calendar:event-42:2026-08-20T06:00:00+00:00",
                "title": "Фактическая тестовая встреча",
                "meeting_url": "https://telemost.yandex.ru/j/1234567890",
                "scheduled_start_at": "2026-08-20T10:00:00+04:00",
                "scheduled_end_at": "2026-08-20T10:30:00+04:00",
                "organizer": "Иван Иванов - ivan@example.com",
                "bot_id": "bot-1",
                "node_id": "node-1",
                "source": "control_service",
                "agenda": "###Повестка:\n#1. Первый вопрос\n#2. Второй вопрос\n###",
            },
            "result": {
                "meeting_started_at": "2026-08-20T10:02:15+04:00",
                "meeting_ended_at": "2026-08-20T10:47:45+04:00",
            },
        }

    def test_completed_task_uses_only_actual_duration(self) -> None:
        outcome = self.repository.upsert_completed_task(
            node_id="node-1",
            task=self.completed_task(),
        )
        self.assertEqual(outcome, "inserted")

        meeting = self.repository.list_meetings()[0]
        self.assertEqual(meeting["meeting_date"], "2026-08-20")
        self.assertEqual(meeting["actual_duration_seconds"], 2730)
        self.assertIsNone(meeting["scheduled_duration_seconds"])
        self.assertEqual(meeting["agenda_source"], "dashboard")
        self.assertEqual(meeting["agenda_items_count"], 2)

    def test_upsert_does_not_duplicate_occurrence(self) -> None:
        task = self.completed_task()
        self.assertEqual(
            self.repository.upsert_completed_task(node_id="node-1", task=task),
            "inserted",
        )
        task["result"]["meeting_ended_at"] = "2026-08-20T10:52:15+04:00"
        self.assertEqual(
            self.repository.upsert_completed_task(node_id="node-1", task=task),
            "updated",
        )
        meetings = self.repository.list_meetings()
        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0]["actual_duration_seconds"], 3000)

    def test_task_without_factual_end_is_not_saved(self) -> None:
        task = self.completed_task()
        task["result"].pop("meeting_ended_at")
        self.assertIsNone(
            self.repository.upsert_completed_task(node_id="node-1", task=task)
        )
        self.assertEqual(self.repository.summary()["total_meetings"], 0)

    def test_summary_uses_actual_duration_and_agenda(self) -> None:
        self.repository.upsert_completed_task(node_id="node-1", task=self.completed_task())
        summary = self.repository.summary()
        self.assertEqual(summary["total_meetings"], 1)
        self.assertEqual(summary["average_actual_duration_seconds"], 2730)
        self.assertEqual(summary["agenda_percentage"], 100.0)
        self.assertEqual(summary["top_organizers"][0]["organizer_email"], "ivan@example.com")

    def test_folder_presence_is_stored_in_sqlite(self) -> None:
        self.repository.upsert_completed_task(node_id="node-1", task=self.completed_task())
        meeting_id = self.repository.list_meetings()[0]["id"]
        self.repository.update_disk_result(
            meeting_id=meeting_id,
            status="not_empty",
            folder_path="/meetings/folder",
            marker_found=False,
            completed=True,
            folder_exists=True,
        )
        meeting = self.repository.list_meetings()[0]
        self.assertTrue(meeting["disk_folder_exists"])
        self.assertEqual(meeting["disk_folder_path"], "/meetings/folder")

        filtered = self.repository.list_meetings(disk_folder_exists=True)
        self.assertEqual(len(filtered), 1)

    def test_disk_scanner_finds_no_speech_marker(self) -> None:
        self.repository.upsert_completed_task(node_id="node-1", task=self.completed_task())

        class FakeDiskReader:
            def __init__(self, token: str) -> None:
                self.token = token

            normalize_path = staticmethod(YandexDiskReader.normalize_path)

            def list_directory(self, path: str) -> list[dict]:
                if path.endswith("/2026/08/20"):
                    return [
                        {
                            "name": "Фактическая тестовая встреча__meeting-1__10-02",
                            "path": "disk:/meetings/folder",
                            "type": "dir",
                        }
                    ]
                return [
                    {
                        "name": "meeting_time.json",
                        "path": "disk:/meetings/folder/meeting_time.json",
                        "type": "file",
                    },
                    {
                        "name": "recording_meeting_pyannote_job_no_speech.txt",
                        "path": "disk:/meetings/folder/no_speech.txt",
                        "type": "file",
                    },
                ]

            def download_json(self, path: str) -> dict:
                return {
                    "title": "Фактическая тестовая встреча",
                    "started_at_astrakhan": "2026-08-20T10:02:15+04:00",
                }

        with patch.dict(
            "os.environ",
            {
                "YANDEX_DISK_TOKEN": "test-token",
                "YANDEX_DISK_BASE_PATH": "/meetings",
            },
        ), patch(
            "control_service.disk_analytics.YandexDiskReader",
            FakeDiskReader,
        ):
            scanner = MeetingDiskAnalyticsScanner(
                self.repository,
                now_provider=lambda: datetime(
                    2026, 8, 20, 12, 0, tzinfo=ZoneInfo("Europe/Astrakhan")
                ),
            )
            result = scanner._scan_once_sync()

        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["empty"], 1)
        meeting = self.repository.list_meetings(disk_empty_status="empty")[0]
        self.assertTrue(meeting["empty_marker_found"])
        self.assertTrue(meeting["disk_scan_completed"])
        self.assertTrue(meeting["disk_folder_exists"])

    def test_final_disk_check_marks_missing_folder(self) -> None:
        self.repository.upsert_completed_task(node_id="node-1", task=self.completed_task())

        class EmptyDiskReader:
            def __init__(self, token: str) -> None:
                self.token = token

            normalize_path = staticmethod(YandexDiskReader.normalize_path)

            def list_directory(self, path: str) -> list[dict]:
                return []

        with patch.dict(
            "os.environ",
            {
                "YANDEX_DISK_TOKEN": "test-token",
                "YANDEX_DISK_BASE_PATH": "/meetings",
            },
        ), patch(
            "control_service.disk_analytics.YandexDiskReader",
            EmptyDiskReader,
        ):
            scanner = MeetingDiskAnalyticsScanner(
                self.repository,
                now_provider=lambda: datetime(
                    2026, 8, 21, 0, 0, tzinfo=ZoneInfo("Europe/Astrakhan")
                ),
            )
            result = scanner._scan_once_sync(date(2026, 8, 20), final_check=True)

        self.assertEqual(result["folders_missing"], 1)
        meeting = self.repository.list_meetings(disk_folder_exists=False)[0]
        self.assertEqual(meeting["disk_empty_status"], "folder_not_found")

    def test_daily_empty_percentage_excludes_unresolved_meetings(self) -> None:
        current_empty = self.completed_task()
        current_empty["metadata"]["external_event_id"] = (
            "calendar:event-empty:2026-08-20T06:00:00+00:00"
        )
        self.repository.upsert_completed_task(node_id="node-1", task=current_empty)

        current_nonempty = deepcopy(current_empty)
        current_nonempty["task_id"] = "task-2"
        current_nonempty["metadata"]["external_event_id"] = (
            "calendar:event-nonempty:2026-08-20T07:00:00+00:00"
        )
        current_nonempty["result"]["meeting_started_at"] = "2026-08-20T11:02:15+04:00"
        current_nonempty["result"]["meeting_ended_at"] = "2026-08-20T11:47:45+04:00"
        self.repository.upsert_completed_task(node_id="node-1", task=current_nonempty)

        unresolved = deepcopy(current_empty)
        unresolved["task_id"] = "task-3"
        unresolved["metadata"]["external_event_id"] = (
            "calendar:event-unknown:2026-08-20T08:00:00+00:00"
        )
        unresolved["result"]["meeting_started_at"] = "2026-08-20T12:02:15+04:00"
        unresolved["result"]["meeting_ended_at"] = "2026-08-20T12:47:45+04:00"
        self.repository.upsert_completed_task(node_id="node-1", task=unresolved)

        previous_nonempty = deepcopy(current_empty)
        previous_nonempty["task_id"] = "task-4"
        previous_nonempty["metadata"]["external_event_id"] = (
            "calendar:event-previous:2026-08-19T06:00:00+00:00"
        )
        previous_nonempty["result"]["meeting_started_at"] = "2026-08-19T10:02:15+04:00"
        previous_nonempty["result"]["meeting_ended_at"] = "2026-08-19T10:47:45+04:00"
        self.repository.upsert_completed_task(node_id="node-1", task=previous_nonempty)

        meetings = self.repository.list_meetings(limit=10)
        by_event = {meeting["event_id"]: meeting for meeting in meetings}
        for event_id, status in (
            ("event-empty", "empty"),
            ("event-nonempty", "not_empty"),
            ("event-previous", "not_empty"),
        ):
            self.repository.update_disk_result(
                meeting_id=by_event[event_id]["id"],
                status=status,
                folder_path=f"/meetings/{event_id}",
                marker_found=status == "empty",
                completed=True,
            )

        daily = self.repository.daily_empty_stats(
            days=30,
            end_date=date(2026, 8, 20),
        )
        self.assertEqual(daily["current_day"]["checked_meetings"], 2)
        self.assertEqual(daily["current_day"]["empty_meetings"], 1)
        self.assertEqual(daily["current_day"]["empty_percentage"], 50.0)
        self.assertEqual(daily["previous_day"]["empty_percentage"], 0.0)
        self.assertEqual(daily["change_from_previous_day_percentage_points"], 50.0)
        self.assertEqual(daily["average_daily_empty_percentage_7_days"], 25.0)
        self.assertEqual(daily["average_daily_empty_percentage_30_days"], 25.0)

        summary = self.repository.summary()
        self.assertEqual(summary["total_meetings"], 4)
        self.assertEqual(summary["disk_checked_meetings"], 3)
        self.assertEqual(summary["empty_percentage"], 33.3)


if __name__ == "__main__":
    unittest.main()
