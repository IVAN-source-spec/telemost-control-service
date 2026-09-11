"""Durable delivery of central monitor states to Uptime Kuma push monitors."""
import asyncio
import copy
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
LINK = 'https://telebot.razum.tools/'


def event(status, kind, detail, session=None, notify=False):
    invitation = 'Откройте дашборд и устраните проблему:' if status == 'down' else 'Подробнее в дашборде:'
    return {'status': status, 'kind': kind, 'session': session,
            'msg': f'{detail} {invitation} {LINK}', '_notify': notify}


def bot_event(bot, period, previous=None, expected_off=False):
    previous = previous or {}
    if previous.get('kind') == 'suspect' and (expected_off or not bot or bot.get('status') == 'unavailable'):
        # Missing telemetry cannot prove that an existing incident recovered.
        return previous
    if expected_off:
        return event('up', 'off', 'AWS штатно выключена; активной встречи не ожидается.')
    if not bot or bot.get('status') == 'unavailable':
        return event('up', 'unavailable', 'Нет актуальных данных от бота.', previous.get('session'))
    session = bot.get('session_id')
    if bot.get('status') == 'idle':
        old = previous.get('session')
        detail = f'Предупреждение по встрече {old} снято: бот завершил участие.' if old else 'Бот свободен; подозрительной встречи нет.'
        return event('up', 'idle', detail, notify=previous.get('kind') == 'suspect')
    single = (bot.get('participant_metrics') or {}).get('single_participant') or {}
    if single.get('alert'):
        elapsed = single.get('monitoring_elapsed_seconds', 0)
        return event('down', 'suspect', f'Подозрительная встреча {session}: один человек, мониторинг {int(elapsed)//60} мин.', session, notify=True)
    if period:
        if previous.get('kind') == 'suspect' and previous.get('session') == session:
            # A controller restart must not silently resolve a known incident.
            return previous
        return event('up', 'normal', f'Встреча {session}: порог мониторинга одного участника не превышен.', session,
                     notify=previous.get('kind') == 'suspect')
    metrics = bot.get('participant_metrics') or {}
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(metrics['measured_at'].replace('Z', '+00:00'))).total_seconds()
        fresh = metrics.get('valid') is True and -5 <= age <= 20
    except (KeyError, AttributeError, TypeError, ValueError):
        fresh = False
    if fresh and metrics.get('other_participants_count') != 1:
        return event('up', 'normal', f'Встреча {session}: предупреждение снято, количество участников изменилось.', session,
                     notify=previous.get('kind') == 'suspect')
    if previous.get('kind') == 'suspect':
        return previous
    return event('up', 'unavailable', 'Данные об участниках устарели.', session)


def session_event(state, previous=None):
    previous = previous or {}
    if not state:
        return previous if previous.get('kind') == 'invalid' else event('up', 'unavailable', 'Не удалось получить состояние сессии Телемоста.')
    status = state.get('status', 'unknown')
    if status in ('valid', 'restored') and state.get('session_valid') is True:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(state['last_checked_at'].replace('Z', '+00:00'))).total_seconds()
            limit = max(120, int(state.get('automatic_check_interval_seconds') or 600) + 120)
            if age < -5 or age > limit:
                raise ValueError('stale')
        except (KeyError, AttributeError, TypeError, ValueError):
            return previous if previous.get('kind') == 'invalid' else event('up', 'unavailable', 'Проверка сессии Телемоста устарела.')
        return event('up', 'valid', 'Сессия Телемоста действительна; авторизация подтверждена.',
                     notify=previous.get('kind') == 'invalid')
    if status == 'unknown':
        return previous if previous.get('kind') == 'invalid' else event('up', 'unknown', 'Валидность сессии Телемоста ещё не подтверждена.')
    return event('down', 'invalid', 'Сессия Телемоста невалидна или требует восстановления. Проверьте раздел «Состояние сессии».', notify=True)


class KumaMonitor:
    def __init__(self, root, audio_monitor, session_service, aws_controller, nodes_loader):
        self.root = Path(root)
        self.audio = audio_monitor
        self.session_service = session_service
        self.aws = aws_controller
        self.nodes_loader = nodes_loader
        self.config_path = self.root / 'config/kuma.json'
        self.state_path = self.root / 'data/kuma_delivery.json'
        self.entries = {}
        if self.state_path.exists():
            self.entries = json.loads(self.state_path.read_text())
        self.config = {}
        self.last_cycle_at = None
        self.last_sent = {}
        self.failures = set()

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(self.entries, stream, ensure_ascii=False)
        os.replace(temp, self.state_path)

    def enqueue(self, key, current):
        current = dict(current)
        notify = current.pop('_notify', False)
        entry = self.entries.setdefault(key, {'queue': []})
        previous = entry.get('desired')
        changed = previous is None or any(previous.get(k) != current.get(k) for k in ('status', 'kind', 'session'))
        if changed:
            if (previous and previous.get('kind') == current.get('kind') == 'suspect'
                    and previous.get('session') and current.get('session')
                    and previous['session'] != current['session']):
                resolved = event('up', 'resolved', f"Встреча {previous['session']} завершена; бот перешёл к другой встрече.")
                resolved.pop('_notify', None)
                entry['queue'].extend((resolved, current))
            elif notify:
                entry['queue'].append(current)
        entry['desired'] = current
        self.save()

    @staticmethod
    def push(url, value):
        # Do not log URLs: their paths contain credentials.
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'kuma.razum.tools' or not parsed.path.startswith('/api/push/'):
            raise ValueError('Unexpected Kuma destination')
        query = urllib.parse.urlencode({'status': value['status'], 'msg': value['msg']})
        req = urllib.request.Request(urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, '')),
                                     headers={'User-Agent': 'Telemost-Control-Monitor/1.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            if json.load(response).get('ok') is not True:
                raise RuntimeError('Kuma rejected state')

    async def deliver(self, key, url, semaphore):
        async with semaphore:
            entry = self.entries.get(key)
            if not entry:
                return
            try:
                while entry['queue']:
                    value = entry['queue'][0]
                    await asyncio.to_thread(self.push, url, value)
                    entry['queue'].pop(0)
                    self.last_sent[key] = time.monotonic()
                    self.save()
                if time.monotonic() - self.last_sent.get(key, 0) >= 30:
                    await asyncio.to_thread(self.push, url, entry['desired'])
                    self.last_sent[key] = time.monotonic()
                self.failures.discard(key)
            except Exception:
                self.failures.add(key)
                log.warning('Kuma delivery deferred: %s', key)

    def status(self):
        return {'enabled': bool(self.config), 'monitors': len(self.config.get('monitors', {})),
                'last_cycle_at': self.last_cycle_at, 'delivery_failures': sorted(self.failures),
                'queued_events': sum(len(v['queue']) for v in self.entries.values())}

    async def run_forever(self):
        session_state = None
        aws_state = {}
        next_services = 0
        while True:
            try:
                if not self.config_path.exists():
                    await asyncio.sleep(5)
                    continue
                self.config = json.loads(self.config_path.read_text())
                if time.monotonic() >= next_services:
                    results = await asyncio.gather(asyncio.to_thread(self.session_service.state),
                                                   asyncio.to_thread(self.aws.status), return_exceptions=True)
                    session_state = results[0] if isinstance(results[0], dict) else None
                    aws_state = results[1] if isinstance(results[1], dict) else {}
                    next_services = time.monotonic() + 30
                targets = self.config.get('monitors', {})
                if 'session' in targets:
                    previous = self.entries.get('session', {}).get('desired')
                    self.enqueue('session', session_event(session_state, previous))
                for node in self.nodes_loader():
                    if node.id not in targets:
                        continue
                    observation = self.audio.observations.get(node.id)
                    if observation is None:
                        continue  # Wait for the first background observation after startup.
                    checked, raw = observation
                    status = self.audio.decorate(copy.deepcopy(raw))
                    bots = status.get('bots') or []
                    bot = bots[0] if bots and time.monotonic() - checked <= 20 else None
                    expected_off = node.lifecycle == 'on_demand' and aws_state.get('ec2_state') == 'stopped'
                    previous = self.entries.get(node.id, {}).get('desired')
                    self.enqueue(node.id, bot_event(bot, self.audio.period(bot) if bot else None, previous, expected_off))
                semaphore = asyncio.Semaphore(6)
                await asyncio.gather(*(self.deliver(k, v['push_url'], semaphore) for k, v in targets.items()))
                self.last_cycle_at = datetime.now(timezone.utc).isoformat()
            except Exception:
                log.warning('Kuma monitoring cycle failed')
            await asyncio.sleep(5)

