import asyncio
import hmac
import html
import json
import os
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from .bot_node_client import BotNodeClient, BotNodeError
from .aws_capacity import AwsCapacityController
from .aws_ec2 import AwsEc2Controller, AwsEc2ControlError
from .config import (
    PROJECT_ROOT,
    BotNodeConfig,
    assignment_service_api_token,
    assignment_service_url,
    control_api_token,
    control_token_required,
    load_env,
    load_nodes,
    session_validator_url,
)
from .dashboard import DASHBOARD_HTML
from .audio_monitor import AudioMonitor
from .kuma_monitor import KumaMonitor
from .agenda_ai import DashboardAgendaService
from .dispatch_guard import active_assignment, meeting_dispatch_lock
from .cohost_client import CohostServiceClient, CohostServiceError
from .employee_directory import EmployeeDirectoryClient, EmployeeDirectoryError


load_env()
from .calendar_monitor import calendar_monitor
from .analytics import (
    MeetingAnalyticsCollector,
    MeetingRepository,
    app_timezone_from_env,
    database_url_from_env,
)
from .auth import AuthError, AuthSession, YandexOAuthService
from .disk_analytics import MeetingDiskAnalyticsScanner
from .session_client import SessionServiceClient, SessionServiceError


meeting_repository = MeetingRepository(database_url_from_env(), app_timezone_from_env())
meeting_analytics = MeetingAnalyticsCollector(
    meeting_repository,
    load_nodes,
    calendar_monitor.read_dispatch_state,
)
meeting_disk_analytics = MeetingDiskAnalyticsScanner(meeting_repository)
session_service = SessionServiceClient(session_validator_url())
auth_service = YandexOAuthService()
aws_ec2_controller = AwsEc2Controller.from_env()
dashboard_agenda_service = DashboardAgendaService()
audio_monitor = AudioMonitor(load_nodes)
kuma_monitor = KumaMonitor(PROJECT_ROOT, audio_monitor, session_service, aws_ec2_controller, load_nodes)
cohost_service = CohostServiceClient()
employee_directory = EmployeeDirectoryClient()


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

    def organizer_email(self) -> str:
        email = str(self.organizer or "").strip().lower()
        if email and "@" not in email:
            raise ValueError("organizer must be an email address")
        return email


class AgendaActivationRequest(BaseModel):
    raw_agenda: str
    source: Optional[str] = "control_dashboard"
    calendar_event_id: Optional[str] = None
    meeting_url: Optional[str] = None
    author: Optional[str] = None


class SessionConfirmationRequest(BaseModel):
    code: str


class SessionAutomaticCheckRequest(BaseModel):
    enabled: bool
    interval_seconds: int = Field(ge=10, le=86400)


class CalendarDiscoveryModeRequest(BaseModel):
    mode: str


class CalendarDiscoveryEventRequest(BaseModel):
    event_key: str


def calendar_discovery_request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    base_url = os.getenv("CALENDAR_DISCOVERY_URL", "http://127.0.0.1:8030").rstrip("/")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body or str(error)
        raise HTTPException(status_code=error.code, detail=detail) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise HTTPException(status_code=502, detail=f"Calendar discovery service is unavailable: {error}") from error
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail="Calendar discovery service returned invalid JSON") from error


def assignment_service_request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    token = assignment_service_api_token()
    if not token:
        raise HTTPException(status_code=503, detail="Assignment service API token is not configured")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{assignment_service_url()}{path}",
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body or str(error)
        raise HTTPException(status_code=error.code, detail=detail) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise HTTPException(status_code=502, detail=f"Assignment service is unavailable: {error}") from error
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail="Assignment service returned invalid JSON") from error


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_service.initialize()
    meeting_repository.initialize()
    kuma_task = asyncio.create_task(kuma_monitor.run_forever())
    audio_monitor_task = asyncio.create_task(audio_monitor.run_forever())
    calendar_task = asyncio.create_task(calendar_monitor.run_forever())
    analytics_task = asyncio.create_task(meeting_analytics.run_forever())
    disk_analytics_task = asyncio.create_task(meeting_disk_analytics.run_forever())
    disk_daily_audit_task = asyncio.create_task(
        meeting_disk_analytics.run_daily_audit_forever()
    )
    aws_capacity_task = asyncio.create_task(aws_capacity_controller.run_forever())
    yield
    calendar_monitor.stop()
    meeting_analytics.stop()
    meeting_disk_analytics.stop()
    aws_capacity_controller.stop()
    kuma_task.cancel()
    audio_monitor_task.cancel()
    calendar_task.cancel()
    analytics_task.cancel()
    disk_analytics_task.cancel()
    disk_daily_audit_task.cancel()
    aws_capacity_task.cancel()
    for task, label in (
        (kuma_task, "Kuma notifications"),
        (audio_monitor_task, "Audio monitor"),
        (calendar_task, "Calendar monitor"),
        (analytics_task, "Meeting analytics"),
        (disk_analytics_task, "Yandex Disk analytics"),
        (disk_daily_audit_task, "Yandex Disk seven-day audit"),
        (aws_capacity_task, "AWS capacity automation"),
    ):
        try:
            await task
        except asyncio.CancelledError:
            print(f"[ControlService] {label} cancelled")


app = FastAPI(
    title="Telemost Control Service",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


from .chat_agenda import router as chat_agenda_router
app.include_router(chat_agenda_router)


def require_control_token(authorization: str | None = Header(default=None)) -> None:
    if not control_token_required():
        return
    expected = control_api_token()
    if not expected:
        raise HTTPException(status_code=500, detail="CONTROL_SERVICE_API_TOKEN is not configured")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid or missing control API token")


def browser_session(request: Request) -> AuthSession | None:
    return auth_service.parse_session(request.cookies.get(auth_service.session_cookie))


def require_control_access(
    request: Request,
    authorization: str | None = Header(default=None),
) -> AuthSession | None:
    if not auth_service.enabled:
        require_control_token(authorization)
        return None
    session = browser_session(request)
    if session is not None:
        return session
    expected = control_api_token()
    if expected and authorization and hmac.compare_digest(authorization, f"Bearer {expected}"):
        return None
    raise HTTPException(status_code=401, detail="Unauthorized")


def nodes() -> list[BotNodeConfig]:
    configured = load_nodes()
    if not configured:
        raise HTTPException(status_code=500, detail="No bot nodes configured")
    return configured


async def node_status(node: BotNodeConfig) -> dict:
    return await asyncio.to_thread(BotNodeClient(node).status)


aws_capacity_controller = AwsCapacityController(
    aws_controller=aws_ec2_controller,
    calendar_monitor=calendar_monitor,
    nodes_loader=load_nodes,
    node_status_reader=node_status,
    action_lock=meeting_dispatch_lock,
    project_root=PROJECT_ROOT,
)
calendar_monitor.add_control_update_callback(aws_capacity_controller.request_evaluation)


def require_admin_access(session: AuthSession | None) -> None:
    if session is not None and not session.is_admin:
        raise HTTPException(status_code=403, detail="Управлять AWS VM может только администратор")


async def read_aws_ec2_status() -> dict:
    try:
        return await asyncio.to_thread(aws_ec2_controller.status)
    except AwsEc2ControlError as error:
        return {
            "configured": aws_ec2_controller.configured,
            "machine_id": aws_ec2_controller.machine_id,
            "instance_id": aws_ec2_controller.instance_id,
            "region": aws_ec2_controller.region,
            "ec2_state": "error",
            "error": str(error),
        }


def merge_aws_ec2_status(machines: list[dict[str, object]], ec2: dict) -> None:
    for machine in machines:
        if machine.get("machine_id") != ec2.get("machine_id"):
            continue
        machine.update({
            "control_configured": bool(ec2.get("configured")),
            "instance_id": ec2.get("instance_id"),
            "region": ec2.get("region"),
            "ec2_state": ec2.get("ec2_state"),
            "ec2_error": ec2.get("error"),
        })
        if ec2.get("public_ip"):
            machine["public_ip"] = ec2["public_ip"]
        state = ec2.get("ec2_state")
        if state in {"pending", "stopping"}:
            machine["status"] = "transitioning"
        elif state in {"stopped", "stopping", "shutting-down", "terminated"}:
            machine["status"] = "unavailable"


def apply_expected_aws_unavailability(
    configured_nodes: list[BotNodeConfig], statuses: list[dict], ec2: dict
) -> None:
    state = str(ec2.get("ec2_state") or "")
    expected = {
        "stopped": ("machine_stopped", "AWS VM выключена"),
        "stopping": ("machine_stopping", "AWS VM выключается"),
        "pending": ("machine_starting", "AWS VM запускается"),
    }.get(state)
    if expected is None:
        return
    reason, message = expected
    for node, node_state in zip(configured_nodes, statuses):
        if node.machine_id != ec2.get("machine_id") or node_state.get("status") == "online":
            continue
        node_state.pop("error", None)
        node_state["availability_reason"] = reason
        node_state["availability_message"] = message
        for bot in node_state.get("bots") or []:
            if bot.get("status") == "unavailable":
                bot["availability_reason"] = reason


def on_demand_machine_statuses(
    configured_nodes: list[BotNodeConfig], statuses: list[dict]
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for node, node_state in zip(configured_nodes, statuses):
        if node.lifecycle != "on_demand" or not node.machine_id:
            continue
        machine = grouped.setdefault(
            node.machine_id,
            {
                "machine_id": node.machine_id,
                "machine_name": node.machine_name or node.machine_id,
                "provider": node.provider,
                "lifecycle": node.lifecycle,
                "public_ip": node.public_ip,
                "nodes_total": 0,
                "nodes_online": 0,
                "bots_capacity": 0,
                "bots_total": 0,
                "bots_idle": 0,
                "bots_busy": 0,
            },
        )
        machine["nodes_total"] = int(machine["nodes_total"]) + 1
        machine["bots_capacity"] = int(machine["bots_capacity"]) + 1
        if node_state.get("status") == "online":
            machine["nodes_online"] = int(machine["nodes_online"]) + 1
        machine["bots_total"] = int(machine["bots_total"]) + int(node_state.get("bots_total") or 0)
        machine["bots_idle"] = int(machine["bots_idle"]) + int(node_state.get("bots_idle") or 0)
        machine["bots_busy"] = int(machine["bots_busy"]) + int(node_state.get("bots_busy") or 0)
    for machine in grouped.values():
        online = int(machine["nodes_online"])
        total = int(machine["nodes_total"])
        machine["status"] = "online" if online == total else "unavailable" if online == 0 else "degraded"
    return list(grouped.values())


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if auth_service.enabled and browser_session(request) is None:
        return RedirectResponse(url="/auth?return_to=/", status_code=303)
    return DASHBOARD_HTML


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_alias(request: Request):
    if auth_service.enabled and browser_session(request) is None:
        return RedirectResponse(url="/auth?return_to=/dashboard", status_code=303)
    return DASHBOARD_HTML


def auth_error_page(message: str, status_code: int = 403) -> HTMLResponse:
    escaped = html.escape(message)
    return HTMLResponse(
        f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Не удалось войти</title><style>
        body{{margin:0;font-family:Arial,sans-serif;background:#f4f7fb;color:#0f172a}}
        main{{max-width:520px;margin:12vh auto;background:white;padding:32px;border-radius:18px;
        box-shadow:0 18px 55px rgba(15,23,42,.12)}}
        a{{display:inline-block;margin-top:18px;padding:12px 18px;border-radius:10px;
        background:#2563eb;color:white;text-decoration:none;font-weight:700}}
        </style></head><body><main><h1>Не удалось войти</h1><p>{escaped}</p>
        <a href="/auth">Повторить вход</a></main></body></html>""",
        status_code=status_code,
    )


@app.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request, return_to: str = Query(default="/")):
    if not auth_service.enabled:
        return RedirectResponse(url="/", status_code=303)
    if browser_session(request) is not None:
        target = return_to if return_to.startswith("/") and not return_to.startswith("//") else "/"
        return RedirectResponse(url=target, status_code=303)
    target = return_to if return_to.startswith("/") and not return_to.startswith("//") else "/"
    encoded_target = urllib.parse.quote(target, safe="/")
    return HTMLResponse(
        f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Вход — Telemost Control</title><style>
        body{{margin:0;font-family:Arial,sans-serif;background:#f4f7fb;color:#0f172a}}
        main{{max-width:460px;margin:14vh auto;background:white;padding:36px;border-radius:18px;
        box-shadow:0 18px 55px rgba(15,23,42,.12);text-align:center}}
        p{{color:#64748b;line-height:1.55}}a{{display:block;margin-top:24px;padding:14px 18px;
        border-radius:10px;background:#2563eb;color:white;text-decoration:none;font-weight:700}}
        </style></head><body><main><h1>Telemost Control</h1>
        <p>Панель доступна только зарегистрированным пользователям.</p>
        <a href="/auth/login?return_to={encoded_target}">Войти через Яндекс</a>
        </main></body></html>"""
    )


@app.get("/auth/login")
async def auth_login(return_to: str = Query(default="/")):
    if not auth_service.enabled:
        return RedirectResponse(url="/", status_code=303)
    state = auth_service.create_state(return_to)
    response = RedirectResponse(auth_service.authorization_url(state), status_code=303)
    response.set_cookie(
        auth_service.state_cookie,
        state,
        max_age=auth_service.state_ttl,
        httponly=True,
        secure=auth_service.cookie_secure,
        samesite="lax",
        path="/auth",
    )
    return response


@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
):
    try:
        if not auth_service.enabled:
            raise AuthError("disabled", "Авторизация пока не включена.", 503)
        if not code or not state:
            raise AuthError("incomplete_callback", "Яндекс не вернул код авторизации.")
        return_to = auth_service.validate_state(
            state, request.cookies.get(auth_service.state_cookie)
        )
        token = auth_service.exchange_code(code)
        session = auth_service.authorize(auth_service.fetch_user(token))
        response = RedirectResponse(url=return_to, status_code=303)
        response.set_cookie(
            auth_service.session_cookie,
            auth_service.create_session(session),
            max_age=auth_service.session_ttl,
            httponly=True,
            secure=auth_service.cookie_secure,
            samesite="lax",
            path="/",
        )
        response.delete_cookie(auth_service.state_cookie, path="/auth")
        return response
    except AuthError as error:
        print(f"[ControlService] OAuth rejected: {error.code} status={error.status_code}")
        return auth_error_page(error.message, error.status_code)


@app.get("/auth/logout")
async def auth_logout():
    response = RedirectResponse(url="/auth", status_code=303)
    response.delete_cookie(auth_service.session_cookie, path="/")
    return response


@app.get("/api/v1/auth/me")
async def auth_me(session: AuthSession | None = Depends(require_control_access)):
    if session is None:
        return {"authenticated": False, "machine_access": True}
    return {
        "authenticated": True,
        "email": session.email,
        "name": session.name,
        "is_admin": session.is_admin,
        "expires_at": session.expires_at,
    }


@app.get("/api/v1/employees")
async def active_employees(
    force: bool = Query(default=False),
    _auth=Depends(require_control_access),
):
    try:
        return await asyncio.to_thread(employee_directory.list_active, force)
    except EmployeeDirectoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/v1/nodes/status")
async def list_node_status(_auth=Depends(require_control_access)):
    configured_nodes = nodes()
    statuses = await asyncio.gather(*(node_status(node) for node in configured_nodes))
    for status in statuses:
        audio_monitor.decorate(status)
    ec2 = await read_aws_ec2_status()
    apply_expected_aws_unavailability(configured_nodes, statuses, ec2)
    bots_total = sum(int(item.get("bots_total") or 0) for item in statuses)
    bots_idle = sum(int(item.get("bots_idle") or 0) for item in statuses)
    bots_busy = sum(int(item.get("bots_busy") or 0) for item in statuses)
    machines = on_demand_machine_statuses(configured_nodes, statuses)
    merge_aws_ec2_status(machines, ec2)
    for machine in machines:
        if machine.get("machine_id") == aws_ec2_controller.machine_id:
            machine["automation"] = aws_capacity_controller.status()
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
        "on_demand_machines": machines,
        "nodes": statuses,
        "kuma": kuma_monitor.status(),
        "audio_monitor": {"last_cycle_at": audio_monitor.last_cycle_at,
                          "start_after_minutes": audio_monitor.start_minutes},
    }


@app.get("/api/v1/aws-machine/status")
async def aws_machine_status(_auth=Depends(require_control_access)):
    return {
        **(await read_aws_ec2_status()),
        "automation": aws_capacity_controller.status(),
    }


@app.get("/api/v1/aws-machine/automation/status")
async def aws_machine_automation_status(_auth=Depends(require_control_access)):
    return aws_capacity_controller.status()


@app.post("/api/v1/aws-machine/start")
async def aws_machine_start(session: AuthSession | None = Depends(require_control_access)):
    require_admin_access(session)
    try:
        result = await asyncio.to_thread(aws_ec2_controller.start)
    except AwsEc2ControlError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    actor = session.email if session is not None else "api-token"
    aws_capacity_controller.record_manual_start()
    print(f"[AwsEc2Control] action=start actor={actor} state={result.get('ec2_state')}")
    return result


@app.post("/api/v1/aws-machine/stop")
async def aws_machine_stop(session: AuthSession | None = Depends(require_control_access)):
    require_admin_access(session)
    async with meeting_dispatch_lock:
        aws_nodes = [
            node for node in nodes()
            if node.lifecycle == "on_demand" and node.machine_id == aws_ec2_controller.machine_id
        ]
        statuses = await asyncio.gather(*(node_status(node) for node in aws_nodes))
        blockers = aws_capacity_controller.stop_blockers(statuses)
        if blockers:
            raise HTTPException(
                status_code=409,
                detail="Нельзя выключить AWS VM: " + ", ".join(blockers),
            )
        try:
            result = await asyncio.to_thread(aws_ec2_controller.stop)
        except AwsEc2ControlError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    actor = session.email if session is not None else "api-token"
    aws_capacity_controller.record_manual_stop()
    print(f"[AwsEc2Control] action=stop actor={actor} state={result.get('ec2_state')}")
    return result


@app.get("/api/v1/analytics/status")
async def analytics_status(_auth=Depends(require_control_access)):
    return {
        "database_url": "configured",
        "timezone": app_timezone_from_env(),
        "poll_interval_seconds": meeting_analytics.interval_seconds,
        "disk_poll_interval_seconds": meeting_disk_analytics.interval_seconds,
        "disk_daily_audit_days": meeting_disk_analytics.daily_audit_days,
        "last_run": meeting_analytics.last_run,
        "disk_last_run": meeting_disk_analytics.last_run,
        "disk_last_daily_audit": meeting_disk_analytics.last_daily_audit,
        "summary": await asyncio.to_thread(meeting_repository.summary),
    }


@app.get("/api/v1/assignments/meetings")
async def assignment_meetings(
    limit: int = Query(default=500, ge=1, le=2000),
    _auth=Depends(require_control_access),
):
    return await asyncio.to_thread(assignment_service_request, f"/api/v1/meetings?limit={limit}")


@app.get("/api/v1/assignments/meetings/{request_id}")
async def assignment_meeting(request_id: str, _auth=Depends(require_control_access)):
    from urllib.parse import quote

    return await asyncio.to_thread(
        assignment_service_request,
        f"/api/v1/meetings/{quote(request_id, safe='')}",
    )


@app.post("/api/v1/assignments/{assignment_id}/retry")
async def assignment_retry(assignment_id: str, _auth=Depends(require_control_access)):
    from urllib.parse import quote

    return await asyncio.to_thread(
        assignment_service_request,
        f"/api/v1/assignments/{quote(assignment_id, safe='')}/retry",
        "POST",
        {},
    )


@app.get("/api/v1/session-state")
async def session_state(_auth=Depends(require_control_access)):
    try:
        return await asyncio.to_thread(session_service.state)
    except SessionServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/v1/session-state/check")
async def session_state_check(_auth=Depends(require_control_access)):
    try:
        return await asyncio.to_thread(session_service.check)
    except SessionServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/v1/session-state/confirm")
async def session_state_confirm(
    request: SessionConfirmationRequest,
    _auth=Depends(require_control_access),
):
    code = "".join(character for character in request.code if character.isdigit())
    if len(code) != 6:
        raise HTTPException(status_code=422, detail="Одноразовый код должен содержать шесть цифр")
    try:
        return await asyncio.to_thread(session_service.confirm, code)
    except SessionServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/v1/session-state/automatic-check")
async def session_state_automatic_check(
    request: SessionAutomaticCheckRequest,
    _auth=Depends(require_control_access),
):
    try:
        return await asyncio.to_thread(
            session_service.configure_automatic_check,
            enabled=request.enabled,
            interval_seconds=request.interval_seconds,
        )
    except SessionServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/v1/analytics/refresh")
async def analytics_refresh(_auth=Depends(require_control_access)):
    meeting_result = await meeting_analytics.collect_once()
    disk_result = await meeting_disk_analytics.scan_once()
    return {"meetings": meeting_result, "yandex_disk": disk_result}


@app.post("/api/v1/analytics/disk-audit")
async def analytics_disk_audit(_auth=Depends(require_control_access)):
    return await meeting_disk_analytics.audit_previous_week()


@app.get("/api/v1/analytics/summary")
async def analytics_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    _auth=Depends(require_control_access),
):
    return await asyncio.to_thread(meeting_repository.summary, date_from, date_to)


@app.get("/api/v1/analytics/daily-empty")
async def analytics_daily_empty(
    days: int = Query(default=30, ge=2, le=366),
    end_date: date | None = Query(default=None),
    _auth=Depends(require_control_access),
):
    return await asyncio.to_thread(
        meeting_repository.daily_empty_stats,
        days=days,
        end_date=end_date,
    )


@app.get("/api/v1/analytics/meetings")
async def analytics_meetings(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    organizer: str | None = Query(default=None),
    agenda_present: bool | None = Query(default=None),
    node_id: str | None = Query(default=None),
    bot_id: str | None = Query(default=None),
    disk_empty_status: str | None = Query(default=None),
    disk_folder_exists: bool | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    _auth=Depends(require_control_access),
):
    meetings = await asyncio.to_thread(
        meeting_repository.list_meetings,
        date_from=date_from,
        date_to=date_to,
        organizer=organizer,
        agenda_present=agenda_present,
        node_id=node_id,
        bot_id=bot_id,
        disk_empty_status=disk_empty_status,
        disk_folder_exists=disk_folder_exists,
        limit=limit,
    )
    return {"count": len(meetings), "meetings": meetings}


def find_node(node_id: str) -> BotNodeConfig:
    for node in nodes():
        if node.id == node_id:
            return node
    raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")


async def select_first_idle_node(statuses: list[dict] | None = None) -> tuple[BotNodeConfig, dict]:
    configured_nodes = nodes()
    if statuses is None:
        statuses = await asyncio.gather(*(node_status(node) for node in configured_nodes))
    for node, status in zip(configured_nodes, statuses):
        if status.get("status") != "online":
            continue
        if int(status.get("bots_idle") or 0) > 0:
            return node, status
    raise HTTPException(status_code=409, detail="No idle bot available on configured nodes")


@app.post("/api/v1/meetings/quick")
async def create_meeting_on_any_node(req: MeetingRequest, _auth=Depends(require_control_access)):
    if not req.meeting_url.strip():
        raise HTTPException(status_code=400, detail="meeting_url is required")
    try:
        organizer_email = req.organizer_email()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    async with meeting_dispatch_lock:
        configured_nodes = nodes()
        statuses = await asyncio.gather(*(node_status(node) for node in configured_nodes))
        existing = active_assignment(statuses, req.meeting_url)
        if existing is not None:
            raise HTTPException(status_code=409, detail={"message": "Meeting is already assigned", **existing})
        node, _status = await select_first_idle_node(statuses)
        payload = req.dict()
        payload["organizer"] = organizer_email or None
        try:
            result = await asyncio.to_thread(BotNodeClient(node).create_meeting_any_bot, payload)
        except BotNodeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    if organizer_email:
        try:
            cohost = await asyncio.to_thread(
                cohost_service.ensure, req.meeting_url, organizer_email
            )
        except CohostServiceError as error:
            cohost = {"status": "failed", "reason": str(error)}
            print(f"[ControlService] Cohost ensure failed for {req.meeting_url}: {error}")
    else:
        cohost = {"status": "skipped", "reason": "organizer_not_selected"}
    return {
        **result,
        "node_id": node.id,
        "node_name": node.name,
        "cohost": cohost,
    }


@app.post("/api/v1/nodes/{node_id}/bots/{bot_id}/meetings")
async def create_meeting_on_specific_bot(
    node_id: str,
    bot_id: str,
    req: MeetingRequest,
    _auth=Depends(require_control_access),
):
    if not req.meeting_url.strip():
        raise HTTPException(status_code=400, detail="meeting_url is required")
    try:
        organizer_email = req.organizer_email()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    async with meeting_dispatch_lock:
        configured_nodes = nodes()
        statuses = await asyncio.gather(*(node_status(item) for item in configured_nodes))
        existing = active_assignment(statuses, req.meeting_url)
        if existing is not None:
            raise HTTPException(status_code=409, detail={"message": "Meeting is already assigned", **existing})
        node = find_node(node_id)
        payload = req.dict()
        payload["organizer"] = organizer_email or None
        try:
            result = await asyncio.to_thread(BotNodeClient(node).create_meeting_for_bot, bot_id, payload)
        except BotNodeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    if organizer_email:
        try:
            cohost = await asyncio.to_thread(
                cohost_service.ensure, req.meeting_url, organizer_email
            )
        except CohostServiceError as error:
            cohost = {"status": "failed", "reason": str(error)}
            print(f"[ControlService] Cohost ensure failed for {req.meeting_url}: {error}")
    else:
        cohost = {"status": "skipped", "reason": "organizer_not_selected"}
    return {
        **result,
        "node_id": node.id,
        "node_name": node.name,
        "cohost": cohost,
    }


class BotLeaveRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=256)


@app.post("/api/v1/nodes/{node_id}/bots/{bot_id}/leave", status_code=202)
async def leave_meeting_on_specific_bot(
    node_id: str,
    bot_id: str,
    req: BotLeaveRequest,
    _auth=Depends(require_control_access),
):
    node = find_node(node_id)
    try:
        result = await asyncio.to_thread(BotNodeClient(node).leave_meeting, bot_id, req.dict())
    except BotNodeError as error:
        status = error.status_code if error.status_code in {404, 409, 422} else 502
        raise HTTPException(status_code=status, detail=str(error)) from error
    print(f"[BotExit] node={node_id} bot={bot_id} session={req.session_id} status={result.get('status')}")
    return {**result, "node_id": node.id, "node_name": node.name}


@app.post("/api/v1/nodes/{node_id}/bots/{bot_id}/agenda/activate")
async def activate_agenda_on_specific_bot(
    node_id: str,
    bot_id: str,
    req: AgendaActivationRequest,
    _auth=Depends(require_control_access),
):
    if not req.raw_agenda.strip():
        raise HTTPException(status_code=400, detail="raw_agenda is required")
    node = find_node(node_id)
    payload = req.dict()
    payload["source"] = payload.get("source") or "control_dashboard"
    try:
        result = await asyncio.to_thread(BotNodeClient(node).activate_agenda, bot_id, payload)
    except BotNodeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        **result,
        "node_id": node.id,
        "node_name": node.name,
        "bot_id": bot_id,
    }


@app.get("/api/v1/calendar/status")
async def calendar_status(_auth=Depends(require_control_access)):
    return calendar_monitor.status()


@app.get("/api/v1/calendar-discovery/status")
async def calendar_discovery_status(_auth=Depends(require_control_access)):
    return await asyncio.to_thread(calendar_discovery_request, "/api/v1/status")


@app.post("/api/v1/calendar-discovery/scan", status_code=202)
async def calendar_discovery_scan(
    refresh_employees: bool = Query(default=False),
    _auth=Depends(require_control_access),
):
    suffix = "?refresh_employees=true" if refresh_employees else ""
    return await asyncio.to_thread(calendar_discovery_request, f"/api/v1/scan{suffix}", "POST")


@app.put("/api/v1/calendar-discovery/management/mode")
async def calendar_discovery_management_mode(
    request: CalendarDiscoveryModeRequest,
    _auth=Depends(require_control_access),
):
    if request.mode not in {"off", "preview", "automatic"}:
        raise HTTPException(status_code=422, detail="Unknown calendar management mode")
    return await asyncio.to_thread(
        calendar_discovery_request,
        "/api/v1/management/mode",
        "PUT",
        {"mode": request.mode},
    )


@app.post("/api/v1/calendar-discovery/management/run", status_code=202)
async def calendar_discovery_management_run(_auth=Depends(require_control_access)):
    return await asyncio.to_thread(calendar_discovery_request, "/api/v1/management/run", "POST")


async def calendar_discovery_event_action(action: str, event_key: str) -> dict:
    return await asyncio.to_thread(
        calendar_discovery_request,
        f"/api/v1/management/{action}",
        "POST",
        {"event_key": event_key},
    )


@app.post("/api/v1/calendar-discovery/management/event")
async def calendar_discovery_management_event(
    request: CalendarDiscoveryEventRequest,
    _auth=Depends(require_control_access),
):
    return await calendar_discovery_event_action("event", request.event_key)


@app.post("/api/v1/calendar-discovery/management/exclude")
async def calendar_discovery_management_exclude(
    request: CalendarDiscoveryEventRequest,
    _auth=Depends(require_control_access),
):
    return await calendar_discovery_event_action("exclude", request.event_key)


@app.post("/api/v1/calendar-discovery/management/include")
async def calendar_discovery_management_include(
    request: CalendarDiscoveryEventRequest,
    _auth=Depends(require_control_access),
):
    return await calendar_discovery_event_action("include", request.event_key)


@app.get("/api/v1/calendar/control/status")
async def calendar_control_status(_auth=Depends(require_control_access)):
    return calendar_monitor.control_status()


@app.get("/api/v1/calendar/upcoming")
async def calendar_upcoming(_auth=Depends(require_control_access)):
    return calendar_monitor.read_upcoming()


@app.post("/api/v1/calendar/upcoming/refresh")
async def calendar_upcoming_refresh(_auth=Depends(require_control_access)):
    try:
        result = await calendar_monitor.refresh_control_now()
        aws_capacity_controller.request_evaluation()
        return result
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/v1/calendar/dispatch-state")
async def calendar_dispatch_state(_auth=Depends(require_control_access)):
    return calendar_monitor.read_dispatch_state()


@app.get("/api/v1/calendar/calendars")
async def calendar_list(_auth=Depends(require_control_access)):
    try:
        calendars = await asyncio.to_thread(calendar_monitor.list_caldav_calendars)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"calendars": calendars}


@app.get("/api/v1/calendar/company/preview")
async def company_calendar_preview(
    days: int = Query(default=2, ge=1, le=14),
    _auth=Depends(require_control_access),
):
    try:
        return await asyncio.to_thread(calendar_monitor.preview_company_events, days)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


class DashboardAgendaInput(BaseModel):
    session_id: str = Field(min_length=1, max_length=256)
    raw_agenda: str = Field(min_length=1, max_length=20000)


@app.post("/api/v1/nodes/{node_id}/bots/{bot_id}/agenda/normalize-activate")
async def normalize_dashboard_agenda(node_id: str, bot_id: str, req: DashboardAgendaInput,
                                    _auth=Depends(require_control_access)):
    if not req.raw_agenda.strip():
        raise HTTPException(status_code=400, detail="Укажите повестку.")
    return await dashboard_agenda_service.activate(find_node(node_id), bot_id, req.session_id, req.raw_agenda)
