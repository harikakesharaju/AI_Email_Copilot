import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Float, Enum, JSON, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class RelationshipType(str, enum.Enum):
    work = "work"
    family = "family"
    friend = "friend"
    recruiter_hr = "recruiter_hr"
    vendor_support = "vendor_support"
    unknown = "unknown"


class DraftStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"
    sent = "sent"


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False)
    google_access_token = Column(Text)
    google_refresh_token = Column(Text)
    gmail_history_id = Column(String)  # tracks last-seen Gmail history for incremental sync
    last_gmail_poll_at = Column(DateTime)  # cursor for incremental unread polls
    created_at = Column(DateTime, default=datetime.utcnow)

    contacts = relationship("Contact", back_populates="user")
    tone_profiles = relationship("ToneProfile", back_populates="user")


class ToneProfile(Base):
    """One row per (user, relationship_type). This is what makes drafts
    sound different for 'work' vs 'family' vs 'recruiter_hr'."""
    __tablename__ = "tone_profiles"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    relationship_type = Column(Enum(RelationshipType), nullable=False)
    # e.g. {"formality": "high", "warmth": "medium", "length": "concise", "enthusiasm": false}
    tone_descriptor = Column(JSON, default=dict)

    user = relationship("User", back_populates="tone_profiles")


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    email = Column(String, nullable=False)
    name = Column(String)
    relationship_type = Column(Enum(RelationshipType), default=RelationshipType.unknown)
    confidence = Column(Float, default=0.0)
    labeled_by_user = Column(Boolean, default=False)  # True once the user confirms/corrects it

    user = relationship("User", back_populates="contacts")


class Thread(Base):
    __tablename__ = "threads"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    gmail_thread_id = Column(String, nullable=False)
    subject = Column(String)
    last_message_at = Column(DateTime)


class Email(Base):
    __tablename__ = "emails"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    thread_id = Column(UUID(as_uuid=False), ForeignKey("threads.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    gmail_message_id = Column(String, unique=True, nullable=False)
    sender = Column(String)
    recipients = Column(JSON, default=list)  # list of contact emails
    body = Column(Text)
    received_at = Column(DateTime)
    category = Column(String)          # WORK, PERSONAL, FINANCE, ...
    priority = Column(String)          # LOW, MEDIUM, HIGH, URGENT
    summary = Column(Text)
    embedding = Column(Vector(384))    # 384 = all-MiniLM-L6-v2 dimension
    awaiting_reply = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)


class Draft(Base):
    __tablename__ = "drafts"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email_id = Column(UUID(as_uuid=False), ForeignKey("emails.id"), nullable=False)
    content = Column(Text)
    status = Column(Enum(DraftStatus), default=DraftStatus.pending)
    confidence = Column(Float, default=0.0)
    mixed_audience = Column(Boolean, default=False)  # True => always hold for review
    gmail_message_id = Column(String)  # Gmail ID of the sent reply, once sent
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    email_id = Column(UUID(as_uuid=False), ForeignKey("emails.id"), nullable=False)
    description = Column(String)
    deadline = Column(DateTime, nullable=True)
    status = Column(String, default="open")


class FeedbackEvent(Base):
    """Captures every draft edit so we can learn per-relationship-type tone over time."""
    __tablename__ = "feedback_events"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    draft_id = Column(UUID(as_uuid=False), ForeignKey("drafts.id"), nullable=False)
    relationship_type = Column(Enum(RelationshipType))
    original_text = Column(Text)
    edited_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
