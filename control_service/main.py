import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .bot_node_client import BotNodeClient, BotNodeError
from .config import (
    BotNodeConfig,
    control_api_token,
    control_token_required,
    load_env,
    load_nodes,
)
from .dashboard import DASHBOARD_HTML


load_env()
from .calendar_monitor import calendar_monitor


class MeetingRequest(BaseModel):
    meeting_url: str
    title: Optional[str] = None
    source: Optional[str] = "control_service"
    external_event_id: Optional[str] = None
    scheduled_start_at: Optional[str] = None
    scheduled_end_at: Optional[str] = None
    organizer: Optional[str] = None
    expected_participants: Optional[str] = None
    agenda: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(calendar_monitor.run_forever())
    yield
    calendar_monitor.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("[ControlService] Calendar monitor cancelled")


app = FastAPI(title="Telemost Control Service", lifespan=lifespan)


def require_control_token(authorization: str | None = Header(default=None)) -> None:
    if not control_token_required():
        return
    expected = control_api_token()
    if not expected:
        raise HTTPException(status_code=500, detail="CONTROL_SERVICE_API_TOKEN is not configured")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid or missing control API token")


def nodes() -> list[BotNodeConfig]:
    configured = load_nodes()
    if not configured:
        raise HTTPException(status_code=500, detail="No bot nodes configured")
    return configured


async def node_status(node: BotNodeConfig) -> dict:
    return await asyncio.to_thread(BotNodeClient(node).status)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_alias():
    return DASHBOARD_HTML


@app.get("/api/v1/nodes/status")
async def list_node_status(_auth=Depends(require_control_token)):
    configured_nodes = nodes()
    statuses = await asyncio.gather(*(node_status(node) for node in configured_nodes))
    bots_total = sum(int(item.get("bots_total") or 0) for item in statuses)
    bots_idle = sum(int(item.get("bots_idle") or 0) for item in statuses)
    bots_busy = sum(int(item.get("bots_busy") or 0) for item in statuses)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "nodes_total": len(statuses),
            "nodes_online": sum(1 for item in statuses if item.get("status") == "online"),
            "nodes_unavailable": sum(1 for item in statuses if item.get("status") != "online"),
            "bots_total": bots_total,
            "bots_idle": bots_idle,
            "bots_busy": bots_busy,
        },
        "nodes": statuses,
    }


def find_node(node_id: str) -> BotNodeConfig:
    for node in nodes():
        if node.id == node_id:
            return node
    raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")


async def select_first_idle_node() -> tuple[BotNodeConfig, dict]:
    configured_nodes = nodes()
    statuses = await asyncio.gather(*(node_status(node) for node in configured_nodes))
    for node, status in zip(configured_nodes, statuses):
        if status.get("status") != "online":
            continue
        if int(status.get("bots_idle") or 0) > 0:
            return node, status
    raise HTTPException(status_code=409, detail="No idle bot available on configured nodes")


@app.post("/api/v1/meetings/quick")
async def create_meeting_on_any_node(req: MeetingRequest, _auth=Depends(require_control_token)):
    if not req.meeting_url.strip():
        raise HTTPException(status_code=400, detail="meeting_url is required")
    node, _status = await select_first_idle_node()
    payload = req.dict()
    try:
        result = await asyncio.to_thread(BotNodeClient(node).create_meeting_any_bot, payload)
    except BotNodeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        **result,
        "node_id": node.id,
        "node_name": node.name,
    }


@app.post("/api/v1/nodes/{node_id}/bots/{bot_id}/meetings")
async def create_meeting_on_specific_bot(
    node_id: str,
    bot_id: str,
    req: MeetingRequest,
    _auth=Depends(require_control_token),
):
    if not req.meeting_url.strip():
        raise HTTPException(status_code=400, detail="meeting_url is required")
    node = find_node(node_id)
    payload = req.dict()
    try:
        result = await asyncio.to_thread(BotNodeClient(node).create_meeting_for_bot, bot_id, payload)
    except BotNodeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        **result,
        "node_id": node.id,
        "node_name": node.name,
    }


@app.get("/api/v1/calendar/status")
async def calendar_status(_auth=Depends(require_control_token)):
    return calendar_monitor.status()


@app.get("/api/v1/calendar/control/status")
async def calendar_control_status(_auth=Depends(require_control_token)):
    return calendar_monitor.control_status()


@app.get("/api/v1/calendar/upcoming")
async def calendar_upcoming(_auth=Depends(require_control_token)):
    return calendar_monitor.read_upcoming()


@app.post("/api/v1/calendar/upcoming/refresh")
async def calendar_upcoming_refresh(_auth=Depends(require_control_token)):
    try:
        return await calendar_monitor.refresh_control_now()
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/v1/calendar/dispatch-state")
async def calendar_dispatch_state(_auth=Depends(require_control_token)):
    return calendar_monitor.read_dispatch_state()


@app.get("/api/v1/calendar/calendars")
async def calendar_list(_auth=Depends(require_control_token)):
    try:
        calendars = await asyncio.to_thread(calendar_monitor.list_caldav_calendars)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"calendars": calendars}


@app.get("/api/v1/calendar/company/preview")
async def company_calendar_preview(
    days: int = Query(default=2, ge=1, le=14),
    _auth=Depends(require_control_token),
):
    try:
        return await asyncio.to_thread(calendar_monitor.preview_company_events, days)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
