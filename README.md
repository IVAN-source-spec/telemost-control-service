# Telemost Control Service

Central control service for multiple `telemost-ai-agent-v3` bot-node instances.

## Features

- Shows one dashboard for multiple bot-node instances.
- Reads node status from `GET /api/v1/node/status`.
- Starts a meeting on any idle bot.
- Starts a meeting on a specific bot on a specific node.
- Passes task metadata to bot-node: `source`, `external_event_id`, `scheduled_start_at`, `scheduled_end_at`, `organizer`.
- Monitors the bot calendar through a private iCalendar/ICS URL.

## Setup

```bash
cp .env.example .env
mkdir -p config
cp config/nodes.example.json config/nodes.json
```

Edit `config/nodes.json`:

```json
[
  {
    "id": "telemost-vm-1",
    "name": "Main VM",
    "base_url": "http://127.0.0.1:8000",
    "token": ""
  }
]
```

If a bot-node has `BOT_NODE_REQUIRE_API_TOKEN=1`, put the same token into `config/nodes.json`.

## Run

```bash
poetry install
poetry run control-service
```

Alternative:

```bash
poetry run python api_run.py
```

Dashboard:

```text
http://<control-service-ip>:8010/
```

Status API:

```bash
curl http://127.0.0.1:8010/api/v1/nodes/status
```

## Calendar Monitor

The control service can monitor the bot account calendar through CalDAV.

`.env` example:

```env
CALENDAR_MONITOR_ENABLED=1
CALENDAR_PROVIDER=caldav
CALENDAR_CALDAV_URL=https://caldav.yandex.ru/
CALENDAR_USERNAME=ai@razum.life
CALENDAR_PASSWORD="application-password-from-yandex-id"
CALENDAR_NAME=
CALENDAR_POLL_INTERVAL_SECONDS=60
CALENDAR_JOIN_BEFORE_MINUTES=2
CALENDAR_JOIN_AFTER_START_MINUTES=30
CALENDAR_TIMEZONE=Europe/Astrakhan
CALENDAR_STATE_FILE=data/calendar_seen.json
```

`CALENDAR_PASSWORD` must be an app password from Yandex ID, not the account password.

The monitor scans event title, description and location for a Telemost link:

```text
https://telemost.yandex.ru/...
```

When an event is ready to join, it sends a task to the first idle bot-node. Duplicate dispatch is prevented by calendar UID:

```text
external_event_id = calendar:<UID>
```

Calendar status:

```bash
curl http://127.0.0.1:8010/api/v1/calendar/status
```

List visible CalDAV calendars:

```bash
curl http://127.0.0.1:8010/api/v1/calendar/calendars
```

If the account has multiple calendars, copy the desired `name` into `CALENDAR_NAME`.

ICS mode is still available as a fallback:

```env
CALENDAR_PROVIDER=ics
CALENDAR_ICS_URL="https://calendar.yandex.ru/export/....ics"
```
