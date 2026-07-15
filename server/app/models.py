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

    request_type: Mapped[str] = mapped_column(String(50), default="")  # e.g. NIC, CDR, IPDR
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    case_officer: Mapped[str] = mapped_column(String(255), default="")
    justification: Mapped[str] = mapped_column(Text, default="")
    request_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="requests")
    identifiers: Mapped[list["RequestIdentifier"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class RequestIdentifier(Base):
    """One number (mobile / NIC / any other) belonging to a request.

    Status lives here, per-number, not on Request: a request with several
    numbers tracks each one's Pending/Sent/Awaited/No Data Found independently,
    since a response for one number doesn't mean the others have arrived.
    Matching an incoming file against `value` (normalized digits) is a single
    indexed query across every number of every request.
    """

    __tablename__ = "request_identifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    value: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default=Status.PENDING, index=True)

    request: Mapped["Request"] = relationship(back_populates="identifiers")
    files: Mapped[list["ResponseFile"]] = relationship(
        back_populates="identifier", cascade="all, delete-orphan"
    )


class ResponseFile(Base):
    """A response file copied into a user's folder for a matched number.

    One row per (file x matched identifier) so a single incoming file that
    matches several numbers (same value+date, possibly across different
    requests/users) naturally records a copy for each one.
    """

    __tablename__ = "response_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifier_id: Mapped[int] = mapped_column(ForeignKey("request_identifiers.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_path: Mapped[str] = mapped_column(String(1000))
    matched_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    identifier: Mapped["RequestIdentifier"] = relationship(back_populates="files")
