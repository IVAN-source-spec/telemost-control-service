from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def maximum_concurrent_meetings(upcoming: dict, now: datetime, window_minutes: int) -> int:
    window_end = now + timedelta(minutes=window_minutes)
    points: list[tuple[datetime, int]] = []
    for event in upcoming.get("events") or []:
        if not event.get("meeting_url"):
            continue
        starts_at = parse_datetime(event.get("starts_at"))
        if starts_at is None:
            continue
        ends_at = parse_datetime(event.get("ends_at")) or starts_at + timedelta(hours=1)
        if ends_at <= now or starts_at >= window_end:
            continue
        start = max(starts_at, now)
        end = min(ends_at, window_end)
        points.append((start, 1))
        points.append((end, -1))

    current = 0
    maximum = 0
    # An ending meeting frees its bot before another meeting starting at the same instant.
    for _, delta in sorted(points, key=lambda item: (item[0], item[1])):
        current += delta
        maximum = max(maximum, current)
    return maximum


def calendar_age_seconds(upcoming: dict, now: datetime) -> float | None:
    generated_at = parse_datetime(upcoming.get("generated_at"))
    if generated_at is None:
        return None
    return max(0.0, (now - generated_at).total_seconds())


class AwsCapacityController:
    def __init__(
        self,
        *,
        aws_controller: Any,
        calendar_monitor: Any,
        nodes_loader: Callable[[], list[Any]],
        node_status_reader: Callable[[Any], Awaitable[dict]],
        action_lock: Any,
        project_root: Path,
    ) -> None:
        self.aws_controller = aws_controller
        self.calendar_monitor = calendar_monitor
        self.nodes_loader = nodes_loader
        self.node_status_reader = node_status_reader
        self.action_lock = action_lock
        self.enabled = os.getenv("AWS_CAPACITY_AUTOMATION_ENABLED", "0").lower() in {
            "1", "true", "yes", "on"
        }
        self.interval_seconds = int(os.getenv("AWS_CAPACITY_INTERVAL_SECONDS", "900"))
        self.window_minutes = int(os.getenv("AWS_CAPACITY_WINDOW_MINUTES", "60"))
        self.reserve_bots = int(os.getenv("AWS_CAPACITY_RESERVE_BOTS", "2"))
        self.calendar_stale_seconds = int(os.getenv("AWS_CAPACITY_CALENDAR_STALE_SECONDS", "180"))
        self.stop_confirmations_required = int(os.getenv("AWS_CAPACITY_STOP_CONFIRMATIONS", "2"))
        self.stop_confirmation_interval_seconds = int(
            os.getenv("AWS_CAPACITY_STOP_CONFIRMATION_INTERVAL_SECONDS", "840")
        )
        self.manual_hold_seconds = int(os.getenv("AWS_CAPACITY_MANUAL_HOLD_SECONDS", "1800"))
        self.auto_min_uptime_seconds = int(os.getenv("AWS_CAPACITY_AUTO_MIN_UPTIME_SECONDS", "1200"))
        self.action_cooldown_seconds = int(os.getenv("AWS_CAPACITY_ACTION_COOLDOWN_SECONDS", "300"))
        state_value = os.getenv("AWS_CAPACITY_STATE_FILE", "data/aws_capacity_state.json")
        state_path = Path(state_value)
        self.state_file = state_path if state_path.is_absolute() else project_root / state_path
        self._state = self._read_state()
        self._stop_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._evaluation_lock = asyncio.Lock()
        self._last_evaluation: dict[str, Any] = {}

    def _read_state(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _write_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        candidate = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        candidate.write_text(json.dumps(self._state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        candidate.replace(self.state_file)

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def request_evaluation(self) -> None:
        self._wake_event.set()

    def record_manual_start(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        self._state.update({
            "manual_hold_until": (now + timedelta(seconds=self.manual_hold_seconds)).isoformat(),
            "last_action": "manual_start",
            "last_action_at": now.isoformat(),
            "stop_confirmations": 0,
            "last_stop_qualified_at": None,
        })
        self._write_state()

    def record_manual_stop(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        self._state.update({
            "manual_hold_until": None,
            "last_action": "manual_stop",
            "last_action_at": now.isoformat(),
            "stop_confirmations": 0,
            "last_stop_qualified_at": None,
        })
        self._write_state()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "window_minutes": self.window_minutes,
            "reserve_bots": self.reserve_bots,
            "calendar_stale_seconds": self.calendar_stale_seconds,
            "stop_confirmations_required": self.stop_confirmations_required,
            "manual_hold_seconds": self.manual_hold_seconds,
            "auto_min_uptime_seconds": self.auto_min_uptime_seconds,
            "last_action": self._state.get("last_action"),
            "last_action_at": self._state.get("last_action_at"),
            "manual_hold_until": self._state.get("manual_hold_until"),
            "stop_confirmations": int(self._state.get("stop_confirmations") or 0),
            "last_evaluation": self._last_evaluation,
        }

    async def run_forever(self) -> None:
        if not self.enabled:
            print("[AwsCapacity] Disabled")
            return
        if not self.aws_controller.configured:
            print("[AwsCapacity] AWS EC2 control is not configured")
            return
        print(f"[AwsCapacity] Started interval={self.interval_seconds}s reserve={self.reserve_bots}")
        while not self._stop_event.is_set():
            self._wake_event.clear()
            try:
                await self.evaluate("scheduled")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._last_evaluation = {
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "decision": "error",
                    "reason": str(error),
                }
                print(f"[AwsCapacity] Evaluation failed: {error}")
            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def _statuses(self, configured_nodes: list[Any]) -> list[dict]:
        return await asyncio.gather(*(self.node_status_reader(node) for node in configured_nodes))

    @staticmethod
    def _idle_bots(statuses: list[dict]) -> int:
        return sum(
            1
            for status in statuses
            if status.get("status") == "online"
            for bot in status.get("bots") or []
            if bot.get("status") == "idle"
        )

    @staticmethod
    def stop_blockers(statuses: list[dict]) -> list[str]:
        blockers: list[str] = []
        for status in statuses:
            node_id = str(status.get("node_id") or "unknown-node")
            if status.get("status") != "online":
                blockers.append(f"{node_id}: состояние узла неизвестно")
                continue
            bots = status.get("bots") or []
            if not bots:
                blockers.append(f"{node_id}: бот не найден")
                continue
            for bot in bots:
                if bot.get("status") != "idle":
                    bot_id = str(bot.get("global_bot_id") or bot.get("bot_id") or node_id)
                    blockers.append(f"{bot_id}: {bot.get('status') or 'unknown'}")
        return blockers

    def _reset_stop_confirmations(self) -> None:
        if self._state.get("stop_confirmations") or self._state.get("last_stop_qualified_at"):
            self._state["stop_confirmations"] = 0
            self._state["last_stop_qualified_at"] = None
            self._write_state()

    def _register_stop_confirmation(self, now: datetime) -> int:
        confirmations = int(self._state.get("stop_confirmations") or 0)
        previous = parse_datetime(self._state.get("last_stop_qualified_at"))
        if confirmations == 0 or previous is None:
            confirmations = 1
            self._state["last_stop_qualified_at"] = now.isoformat()
        elif (now - previous).total_seconds() >= self.stop_confirmation_interval_seconds:
            confirmations += 1
            self._state["last_stop_qualified_at"] = now.isoformat()
        self._state["stop_confirmations"] = confirmations
        self._write_state()
        return confirmations

    def _cooldown_active(self, now: datetime) -> bool:
        last_action_at = parse_datetime(self._state.get("last_action_at"))
        return bool(
            last_action_at
            and (now - last_action_at).total_seconds() < self.action_cooldown_seconds
        )

    def _minimum_uptime_active(self, now: datetime, ec2: dict) -> bool:
        launched_at = parse_datetime(ec2.get("launched_at"))
        if launched_at is None:
            launched_at = parse_datetime(self._state.get("automatic_started_at"))
        return bool(
            launched_at
            and (now - launched_at).total_seconds() < self.auto_min_uptime_seconds
        )

    async def evaluate(self, trigger: str = "manual_refresh") -> dict[str, Any]:
        async with self._evaluation_lock:
            now = datetime.now(timezone.utc)
            upcoming = self.calendar_monitor.read_upcoming()
            calendar_age = calendar_age_seconds(upcoming, now)
            calendar_fresh = calendar_age is not None and calendar_age <= self.calendar_stale_seconds
            meetings = maximum_concurrent_meetings(upcoming, now, self.window_minutes)
            configured_nodes = self.nodes_loader()
            persistent_nodes = [node for node in configured_nodes if node.lifecycle != "on_demand"]
            aws_nodes = [
                node for node in configured_nodes
                if node.lifecycle == "on_demand" and node.machine_id == self.aws_controller.machine_id
            ]
            persistent_statuses = await self._statuses(persistent_nodes)
            free_persistent = self._idle_bots(persistent_statuses)
            required_capacity = meetings + self.reserve_bots
            start_required = free_persistent < required_capacity
            ec2 = await asyncio.to_thread(self.aws_controller.status)
            ec2_state = str(ec2.get("ec2_state") or "unknown")

            evaluation: dict[str, Any] = {
                "checked_at": now.isoformat(),
                "trigger": trigger,
                "ec2_state": ec2_state,
                "calendar_fresh": calendar_fresh,
                "calendar_age_seconds": round(calendar_age, 1) if calendar_age is not None else None,
                "maximum_concurrent_meetings": meetings,
                "free_persistent_bots": free_persistent,
                "required_capacity": required_capacity,
                "decision": "none",
                "reason": "capacity_sufficient",
            }

            if not calendar_fresh:
                self._reset_stop_confirmations()
                evaluation.update(decision="blocked", reason="calendar_stale")
                self._last_evaluation = evaluation
                return evaluation

            if ec2_state in {"stopped", "stopping"}:
                self._reset_stop_confirmations()
                if start_required and ec2_state == "stopped" and not self._cooldown_active(now):
                    async with self.action_lock:
                        result = await asyncio.to_thread(self.aws_controller.start)
                    self._state.update({
                        "last_action": "automatic_start",
                        "last_action_at": now.isoformat(),
                        "automatic_started_at": now.isoformat(),
                    })
                    self._write_state()
                    evaluation.update(
                        decision="start",
                        reason="persistent_capacity_below_calendar_demand",
                        ec2_state=result.get("ec2_state"),
                    )
                    print(
                        f"[AwsCapacity] Automatic start: free={free_persistent} "
                        f"meetings={meetings} reserve={self.reserve_bots}"
                    )
                elif start_required:
                    evaluation.update(decision="wait", reason="machine_transition_or_action_cooldown")
                self._last_evaluation = evaluation
                return evaluation

            if ec2_state != "running":
                self._reset_stop_confirmations()
                evaluation.update(decision="wait", reason="machine_not_stable")
                self._last_evaluation = evaluation
                return evaluation

            if start_required:
                self._reset_stop_confirmations()
                evaluation["reason"] = "aws_capacity_still_required"
                self._last_evaluation = evaluation
                return evaluation

            hold_until = parse_datetime(self._state.get("manual_hold_until"))
            if hold_until and now < hold_until:
                self._reset_stop_confirmations()
                evaluation.update(decision="wait", reason="manual_start_hold", manual_hold_until=hold_until.isoformat())
                self._last_evaluation = evaluation
                return evaluation

            if self._cooldown_active(now):
                self._reset_stop_confirmations()
                evaluation.update(decision="wait", reason="action_cooldown")
                self._last_evaluation = evaluation
                return evaluation

            if self._minimum_uptime_active(now, ec2):
                self._reset_stop_confirmations()
                evaluation.update(decision="wait", reason="minimum_uptime")
                self._last_evaluation = evaluation
                return evaluation

            aws_statuses = await self._statuses(aws_nodes)
            blockers = self.stop_blockers(aws_statuses)
            if blockers:
                self._reset_stop_confirmations()
                evaluation.update(decision="blocked", reason="aws_bots_not_idle", blockers=blockers)
                self._last_evaluation = evaluation
                return evaluation

            confirmations = self._register_stop_confirmation(now)
            evaluation["stop_confirmations"] = confirmations
            if confirmations < self.stop_confirmations_required:
                evaluation.update(decision="wait", reason="awaiting_second_stop_confirmation")
                self._last_evaluation = evaluation
                return evaluation

            # Recheck calendar and every AWS bot while holding the dispatch lock.
            async with self.action_lock:
                latest_upcoming = self.calendar_monitor.read_upcoming()
                latest_age = calendar_age_seconds(latest_upcoming, datetime.now(timezone.utc))
                latest_meetings = maximum_concurrent_meetings(
                    latest_upcoming, datetime.now(timezone.utc), self.window_minutes
                )
                latest_persistent_statuses = await self._statuses(persistent_nodes)
                latest_free_persistent = self._idle_bots(latest_persistent_statuses)
                latest_statuses = await self._statuses(aws_nodes)
                latest_blockers = self.stop_blockers(latest_statuses)
                if (
                    latest_age is None
                    or latest_age > self.calendar_stale_seconds
                    or latest_free_persistent < latest_meetings + self.reserve_bots
                    or latest_blockers
                ):
                    self._reset_stop_confirmations()
                    evaluation.update(decision="blocked", reason="final_safety_recheck_failed")
                    self._last_evaluation = evaluation
                    return evaluation
                result = await asyncio.to_thread(self.aws_controller.stop)

            self._state.update({
                "last_action": "automatic_stop",
                "last_action_at": now.isoformat(),
                "automatic_started_at": None,
                "stop_confirmations": 0,
                "last_stop_qualified_at": None,
            })
            self._write_state()
            evaluation.update(decision="stop", reason="persistent_capacity_sufficient", ec2_state=result.get("ec2_state"))
            self._last_evaluation = evaluation
            print(
                f"[AwsCapacity] Automatic stop: free={free_persistent} "
                f"meetings={meetings} reserve={self.reserve_bots}"
            )
            return evaluation
