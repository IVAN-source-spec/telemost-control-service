"""In-memory calendar agenda extraction, consumed only on a fresh calendar poll."""
import asyncio
import os
import time
import urllib.parse

from .agenda_ai import normalize, AIUnavailable, InvalidAIResult
from .bot_node_client import BotNodeError


class CalendarAgendaService:
    def __init__(self, normalizer=normalize):
        self.normalizer = normalizer
        self.entries = {}
        self.jobs = set()
        self.retry_seconds = max(10, int(os.getenv('CALENDAR_AGENDA_AI_RETRY_SECONDS', '60')))
        self.concurrency = max(1, int(os.getenv('CALENDAR_AGENDA_AI_CONCURRENCY', '2')))

    def retain(self, keys):
        # Detached inference may finish, but has no reference back to a meeting.
        for key in set(self.entries) - set(keys):
            del self.entries[key]

    def stop(self):
        self.entries.clear()
        for task in tuple(self.jobs):
            task.cancel()

    async def infer(self, raw):
        try:
            return 'ready', await asyncio.to_thread(self.normalizer, raw)
        except AIUnavailable:
            return 'ai_unavailable', None
        except InvalidAIResult:
            return 'invalid_ai_result', None
        except Exception:
            return 'ai_unavailable', None

    async def step(self, key, description, candidate, client, bot_id, session_id):
        entry = self.entries.get(key)
        if entry is None or entry['description'] != description:
            entry = {'description': description, 'retry_at': 0}
            self.entries[key] = entry
        if not description.strip():
            return {'status': 'watching'}
        if time.monotonic() < entry['retry_at']:
            return {'status': 'watching'}
        path = '/api/v1/bots/' + urllib.parse.quote(bot_id, safe='') + '/agenda/dashboard'

        async def command(action, raw):
            return await asyncio.to_thread(client.request_json, 'POST', path, {
                'session_id': session_id, 'source': 'calendar_monitor',
                'action': action, 'raw_agenda': raw,
            })

        try:
            if 'validated' not in entry:
                # Prefer the explicit block; otherwise let the actual bot parser decide.
                raw = candidate or description
                if len(raw) <= 20000:
                    result = await command('validate', raw)
                    if result.get('status') == 'already_active':
                        return result
                    if result.get('status') not in ('valid_agenda', 'invalid_agenda'):
                        return result
                    if result['status'] == 'valid_agenda':
                        entry['agenda'] = raw
                entry['validated'] = True
            if 'agenda' not in entry:
                task = entry.get('task')
                if task is None:
                    if len(self.jobs) >= self.concurrency:
                        return {'status': 'processing'}
                    task = asyncio.create_task(self.infer(description))
                    self.jobs.add(task)
                    task.add_done_callback(self.jobs.discard)
                    entry['task'] = task
                    return {'status': 'processing'}
                if not task.done():
                    return {'status': 'processing'}
                state, agenda = task.result()
                del entry['task']
                if state != 'ready':
                    entry['retry_at'] = time.monotonic() + self.retry_seconds
                    return {'status': state}
                entry['agenda'] = agenda
            agenda = entry['agenda']
            if agenda is None:
                return {'status': 'watching'}
            # The bot validates again and checks the session inside its activation lock.
            result = await command('activate', agenda)
            if result.get('status') == 'invalid_agenda':
                entry.pop('agenda', None)
                entry['retry_at'] = time.monotonic() + self.retry_seconds
            return result
        except BotNodeError as error:
            if error.status_code in (404, 409):
                self.entries.pop(key, None)
                return {'status': 'meeting_ended'}
            entry['retry_at'] = time.monotonic() + self.retry_seconds
            return {'status': 'bot_unavailable'}
