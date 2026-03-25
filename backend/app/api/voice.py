"""Voice / streaming endpoint using Server-Sent Events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.billing import UsageType
from app.models.user import User
from app.services import llm_analyzer, usage

router = APIRouter(prefix="/voice", tags=["voice"])


class StreamAskRequest(BaseModel):
    question: str


@router.post("/ask/stream")
async def ask_stream(
    body: StreamAskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream AI response via Server-Sent Events."""
    if not await usage.check_ai_quota(db, user.id):
        raise HTTPException(status_code=429, detail="Monthly AI query limit reached. Upgrade to Pro.")

    await usage.track_usage(db, user.id, UsageType.AI_QUERY)

    async def event_generator():
        async for chunk in llm_analyzer.ask_stream(db, user.id, body.question):
            yield {"data": chunk}

    return EventSourceResponse(event_generator())
