"""Database models"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Conversation(Base):
    """Conversation model for storing LLM interactions"""
    
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Index for efficient history queries
    __table_args__ = (
        Index('idx_conversations_created_at', 'created_at'),
    )
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": str(self.id),
            "prompt": self.prompt,
            "response": self.response,
            "created_at": self.created_at.isoformat(),
        }

