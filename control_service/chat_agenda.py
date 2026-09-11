"""Authenticated, stateless agenda normalization for meeting chat clients."""
import asyncio
import hmac
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .agenda_ai import normalize, AIUnavailable, InvalidAIResult
from .bot_node_client import BotNodeClient, BotNodeError
from .config import load_nodes

router = APIRouter()
pending = set()


class ChatAgendaInput(BaseModel):
    node_id: str = Field(min_length=1, max_length=256)
    bot_id: str = Field(min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=256)
    raw_agenda: str = Field(min_length=1, max_length=20000)


@router.post('/api/v1/chat-agenda/normalize')
async def normalize_chat_agenda(req: ChatAgendaInput, authorization: str | None = Header(default=None)):
    token = os.getenv('CHAT_AGENDA_API_TOKEN', '')
    if not token or not hmac.compare_digest((authorization or '').encode(), ('Bearer ' + token).encode()):
        raise HTTPException(status_code=401, detail='Unauthorized')
    node = next((n for n in load_nodes() if n.id == req.node_id), None)
    if node is None:
        raise HTTPException(status_code=404, detail='Unknown node')
    key = (req.node_id, req.bot_id, req.session_id)
    if key in pending:
        return {'status': 'processing'}
    pending.add(key)
    client = BotNodeClient(node, timeout_seconds=5)

    async def current():
        state = await asyncio.to_thread(client.agenda_status, req.bot_id)
        if state.get('session_id') != req.session_id or not state.get('meeting_started'):
            return {'status': 'meeting_ended'}
        if state.get('agenda_active'):
            return {'status': 'already_active'}
        return None

    try:
        state = await current()
        if state:
            return state
        try:
            result = await asyncio.to_thread(normalize, req.raw_agenda)
            answer = {'status': 'normalized', 'raw_agenda': result} if result else {'status': 'agenda_not_found'}
        except AIUnavailable:
            answer = {'status': 'ai_unavailable'}
        except InvalidAIResult:
            answer = {'status': 'invalid_ai_result'}
        state = await current()
        return state or answer
    except BotNodeError as error:
        return {'status': 'meeting_ended' if error.status_code in (404, 409) else 'ai_unavailable'}
    finally:
        pending.discard(key)
