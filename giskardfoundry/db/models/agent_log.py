"""Agent log model."""

from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class AgentLog(Base):
    __tablename__ = "agent_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[Any] = mapped_column(DateTime(timezone=True), default=func.now())
    agent_name: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
