from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

from .engine import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    trust_level: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    policy_yaml: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="workspace")
    memory_records: Mapped[List["MemoryRecord"]] = relationship("MemoryRecord", back_populates="workspace")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="workspace")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    backend_used: Mapped[str] = mapped_column(String(64), default="unknown")
    model_used: Mapped[str] = mapped_column(String(128), default="unknown")
    messages: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    trust_level: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    channel: Mapped[str] = mapped_column(String(64), default="web")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="sessions")


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    memory_class: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trust_level: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    retention_class: Mapped[str] = mapped_column(String(32), default="persistent")
    provenance: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), default="text")

    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536) if HAS_PGVECTOR else JSON, nullable=True
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="memory_records")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    workspace_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("workspaces.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(256), nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    policy_decision: Mapped[str] = mapped_column(String(32), default="unknown")
    approval_status: Mapped[str] = mapped_column(String(32), default="not_required")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace", back_populates="audit_logs")


class PolicyConfig(Base):
    __tablename__ = "policy_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), unique=True, nullable=False)
    config_yaml: Mapped[str] = mapped_column(Text, default="")
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
