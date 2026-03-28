"""Workflow event model."""

from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class WorkflowEvent(Base):
    __tablename__ = "workflow_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[Any] = mapped_column(DateTime(timezone=True), default=func.now())
    workflow_name: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(50))
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
