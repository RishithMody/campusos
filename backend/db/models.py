from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    contact_handle: Mapped[str] = mapped_column(String(80), unique=True)
    agent_id: Mapped[str] = mapped_column(String(80), unique=True)
    ceiling: Mapped[str] = mapped_column(String(20), default="free_busy")
    discord_id: Mapped[str | None] = mapped_column(String(80))


class Negotiation(Base):
    __tablename__ = "negotiations"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    __mapper_args__ = {"version_id_col": version}


class Grant(Base):
    __tablename__ = "grants"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    agent: Mapped[str] = mapped_column(String(80), index=True)
    negotiation: Mapped[str] = mapped_column(ForeignKey("negotiations.id"), index=True)
    level: Mapped[str] = mapped_column(String(20))
    expires: Mapped[str] = mapped_column(String(50))
    revoked: Mapped[bool] = mapped_column(default=False)


class Commitment(Base):
    __tablename__ = "commitments"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    negotiation: Mapped[str] = mapped_column(ForeignKey("negotiations.id"), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[str | None] = mapped_column(String(20))
    decided_at: Mapped[str | None] = mapped_column(String(50))
    decided_version: Mapped[int | None] = mapped_column(Integer)


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    platform_id: Mapped[str] = mapped_column(String(80), unique=True)
    guild: Mapped[str] = mapped_column(String(80))
    bot: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    at: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text, default="")
