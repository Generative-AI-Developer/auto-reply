from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# --- Status constants ---------------------------------------------------------
class Status:
    PENDING = "Pending"
    SENT = "Sent"
    AWAITED = "Awaited"
    NO_DATA_FOUND = "No Data Found"

    ALL = (PENDING, SENT, AWAITED, NO_DATA_FOUND)
    # Only these may be set manually by an operator; SENT is driven by the watcher.
    MANUAL = (AWAITED, NO_DATA_FOUND)


class Role:
    ADMIN = "admin"
    USER = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    zone_section: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default=Role.USER)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    requests: Mapped[list["Request"]] = relationship(back_populates="owner")


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    case_officer: Mapped[str] = mapped_column(String(255), default="")
    justification: Mapped[str] = mapped_column(Text, default="")
    request_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), default=Status.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="requests")
    identifiers: Mapped[list["RequestIdentifier"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    files: Mapped[list["ResponseFile"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class RequestIdentifier(Base):
    """One number (mobile / NIC / any other) belonging to a request.

    A request may have many; matching an incoming file against `value` (normalized
    digits) is a single indexed query across every number of every request.
    """

    __tablename__ = "request_identifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    value: Mapped[str] = mapped_column(String(50), index=True)

    request: Mapped["Request"] = relationship(back_populates="identifiers")


class ResponseFile(Base):
    """A response file copied into a user's folder for a matched request.

    One row per (file x matched request) so a single incoming file that matches
    several requests naturally records a copy in each owner's folder.
    """

    __tablename__ = "response_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_path: Mapped[str] = mapped_column(String(1000))
    matched_value: Mapped[str] = mapped_column(String(50), default="")
    matched_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    request: Mapped["Request"] = relationship(back_populates="files")
