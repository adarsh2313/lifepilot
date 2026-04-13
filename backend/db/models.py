from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    horizon: Mapped[str] = mapped_column(String(20), nullable=False)  # weekly | monthly | custom
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)   # YYYY-MM-DD
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    progress: Mapped[str] = mapped_column(String(20), default="not_started", nullable=False)
    # weekly goals use ISO week string e.g. "2024-W15", monthly use "2024-04"
    period: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("goals.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    threads: Mapped[list["Thread"]] = relationship("Thread", back_populates="goal", foreign_keys="Thread.goal_id")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)             # YYYY-MM-DD
    session_type: Mapped[str] = mapped_column(String(10), nullable=False)     # morning | evening
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON list of {role, content}
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON
    threads_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True) # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("goals.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    goal: Mapped["Goal | None"] = relationship("Goal", back_populates="threads", foreign_keys=[goal_id])
