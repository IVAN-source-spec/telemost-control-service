"""Background policy for single-participant audio monitoring; no browser required."""
import asyncio
import logging
import math
import os
import time
from datetime import datetime, timezone

from .bot_node_client import BotNodeClient

log = logging.getLogger(__name__)


def minutes(name, default):
    try:
        value = float(os.getenv(name, str(default)))
        if math.isfinite(value) and value >= 0:
            return value
    except ValueError:
        pass
    log.warning('Invalid %s; using %s', name, default)
    return default


class AudioMonitor:
    def __init__(self, nodes_loader, client_factory=BotNodeClient, clock=time.monotonic):
        self.nodes_loader = nodes_loader
        self.client_factory = client_factory
        self.clock = clock
        self.start_minutes = minutes('TELEMOST_SINGLE_PARTICIPANT_AUDIO_START_MINUTES', 1)
        self.alert_minutes = minutes('TELEMOST_SINGLE_PARTICIPANT_ALERT_MINUTES', 30)
        self.states = {}
        self.observations = {}
        self.last_cycle_at = None

    @staticmethod
    def period(bot):
        metrics = bot.get('participant_metrics') or {}
        single = metrics.get('single_participant') or {}
        try:
            raw_stamp = metrics.get('measured_at')
            if not isinstance(raw_stamp, str):
                return None
            stamp = datetime.fromisoformat(raw_stamp.replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
        except (KeyError, ValueError, TypeError):
            return None
        if (bot.get('status') not in ('idle', 'unavailable') and bot.get('session_id')
                and metrics.get('session_id') == bot['session_id']
                and metrics.get('valid') is True and -5 <= age <= 20
                and metrics.get('other_participants_count') == 1
                and single.get('active') and single.get('started_at')):
            return single['started_at']
        return None

    async def poll(self, node):
        client = self.client_factory(node, timeout_seconds=5)
        status = await asyncio.to_thread(client.status)
        self.observations[node.id] = (self.clock(), status)
        seen = set()
        for bot in status.get('bots', []):
            key = (node.id, bot['bot_id'])
            seen.add(key)
            period = self.period(bot)
            session = bot.get('session_id')
            now = self.clock()
            old = self.states.get(key)
            if old and (old['session_id'] != session or old['period_id'] != period
                        or now - old['checked'] > 20):
                # Clear the policy state before I/O so the UI immediately stops trusting it.
                self.states.pop(key, None)
                if old['session_id'] == session:
                    try:
                        await asyncio.to_thread(client.audio_monitor, bot['bot_id'], {
                            'session_id': session, 'period_id': old['period_id'], 'action': 'reset'})
                    except Exception:
                        log.warning('Audio reset not acknowledged: %s', node.id)
                old = None
            if not period:
                continue
            state = old or {'session_id': session, 'period_id': period, 'started': now}
            state.update(checked=now, error=None)
            self.states[key] = state
            if now - state['started'] >= self.start_minutes * 60:
                try:
                    result = await asyncio.to_thread(client.audio_monitor, bot['bot_id'], {
                        'session_id': session, 'period_id': period, 'action': 'start'})
                    if result.get('accepted') is not True:
                        raise RuntimeError('Audio start was not accepted')
                    if 'monitoring_started' not in state:
                        state['monitoring_started'] = self.clock()
                        state['monitoring_started_at'] = datetime.now(timezone.utc).isoformat()
                except Exception:
                    state['error'] = 'Команда накопления не подтверждена'
                    log.warning('Audio start not acknowledged: %s', node.id)
        for key in list(self.states):
            if key[0] == node.id and key not in seen:
                self.states.pop(key, None)

    def decorate(self, status):
        for bot in status.get('bots', []):
            metrics = bot.get('participant_metrics')
            if not metrics:
                continue
            state = self.states.get((status['node_id'], bot['bot_id']))
            period = self.period(bot)
            fresh = bool(state and period and state['period_id'] == period
                         and state['session_id'] == bot.get('session_id')
                         and self.clock() - state['checked'] <= 20)
            elapsed = max(0, self.clock() - state['started']) if fresh else 0
            monitoring = bool(fresh and 'monitoring_started' in state)
            monitoring_elapsed = max(0, self.clock() - state['monitoring_started']) if monitoring else 0
            alert = bool(monitoring and self.alert_minutes > 0
                         and monitoring_elapsed >= self.alert_minutes * 60)
            metrics['single_participant'] = {
                **(metrics.get('single_participant') or {}),
                'elapsed_seconds': int(elapsed), 'active': fresh,
                'monitoring_active': monitoring,
                'monitoring_elapsed_seconds': int(monitoring_elapsed),
                'monitoring_started_at': state.get('monitoring_started_at') if monitoring else None,
                'enabled': self.alert_minutes > 0,
                'threshold_minutes': self.alert_minutes, 'alert': alert,
                'managed_by': 'control_service',
            }
            audio = metrics.get('audio_activity')
            if audio:
                audio['start_after_minutes'] = self.start_minutes
                audio['remaining_seconds'] = max(0, int(self.start_minutes * 60 - elapsed))
                audio['monitor_error'] = state.get('error') if fresh else None
                if not fresh:
                    audio['status'] = 'waiting_monitor' if period else 'not_single_participant'
                    audio['valid'] = False
                elif elapsed < self.start_minutes * 60:
                    audio['status'] = 'waiting_threshold'
                    audio['valid'] = False
        return status

    async def run_forever(self):
        while True:
            try:
                nodes = self.nodes_loader()
                results = await asyncio.gather(*(self.poll(n) for n in nodes), return_exceptions=True)
                for node, result in zip(nodes, results):
                    if isinstance(result, Exception):
                        log.warning('Audio monitor polling failed: %s', node.id)
                self.last_cycle_at = datetime.now(timezone.utc).isoformat()
                ids = {n.id for n in nodes}
                for key in list(self.states):
                    if key[0] not in ids:
                        self.states.pop(key, None)
            except Exception:
                log.exception('Audio monitor cycle failed')
            await asyncio.sleep(5)
