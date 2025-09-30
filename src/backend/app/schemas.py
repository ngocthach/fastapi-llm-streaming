"""Pydantic schemas for request/response validation"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class StreamRequest(BaseModel):
    """Request schema for streaming endpoint"""
    prompt: str = Field(..., min_length=1, max_length=10000, description="The prompt to send to the LLM")


class ConversationResponse(BaseModel):
    """Response schema for conversation data"""
    id: str
    prompt: str
    response: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Response schema for conversation list"""
    conversations: List[ConversationResponse]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    """Response schema for health check"""
    status: str
    timestamp: datetime
    database: str = "unknown"

