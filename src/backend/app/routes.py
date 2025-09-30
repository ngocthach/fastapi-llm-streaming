"""API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import AsyncGenerator
from datetime import datetime
import uuid

from app.database import get_db
from app.models import Conversation
from app.schemas import (
    StreamRequest,
    ConversationResponse,
    ConversationListResponse,
    HealthResponse,
)
from app.llm import get_llm_streamer
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint"""
    db_status = "unknown"

    try:
        # Test database connection
        await db.execute(select(1))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow(),
        database=db_status,
    )


@router.get("/history", response_model=ConversationListResponse)
async def get_history(
    limit: int = settings.default_page_limit,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Get conversation history with pagination"""
    # Validate pagination parameters
    if limit < 1 or limit > settings.max_page_limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Limit must be between 1 and {settings.max_page_limit}",
        )

    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Offset must be non-negative",
        )

    try:
        # Get total count
        count_query = select(func.count(Conversation.id))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get conversations ordered by created_at descending
        query = (
            select(Conversation)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        conversations = result.scalars().all()

        return ConversationListResponse(
            conversations=[
                ConversationResponse(
                    id=str(conv.id),
                    prompt=conv.prompt,
                    response=conv.response,
                    created_at=conv.created_at,
                )
                for conv in conversations
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.get("/history/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific conversation by ID"""
    # Validate UUID format
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID format",
        )

    try:
        query = select(Conversation).where(Conversation.id == conv_uuid)
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        return ConversationResponse(
            id=str(conversation.id),
            prompt=conversation.prompt,
            response=conversation.response,
            created_at=conversation.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


async def _persist_conversation(db: AsyncSession, prompt: str, response: str) -> None:
    try:
        conv = Conversation(prompt=prompt, response=response)
        db.add(conv)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


@router.post("/stream")
async def stream(request: StreamRequest, db: AsyncSession = Depends(get_db)):
    """Stream LLM response chunk-by-chunk and persist full/partial result"""
    prompt = request.prompt.strip()

    async def event_stream() -> AsyncGenerator[str, None]:
        full_text = ""
        try:
            streamer = get_llm_streamer()
            async for chunk in streamer(prompt):
                full_text += chunk
                yield chunk
        except Exception as e:
            # Persist partial response then re-raise
            try:
                await _persist_conversation(db, prompt, full_text)
            finally:
                raise e
        else:
            # Persist full response
            await _persist_conversation(db, prompt, full_text)

    return StreamingResponse(event_stream(), media_type="text/plain")
