from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    """request_id (REQ-00001, ...) is system-generated and permanent.

    request_number is user-supplied at creation time and unique per owner
    (nullable only because requests created before this field existed have
    none). Submitting the same request_number again for the same owner
    merges the new numbers into that existing request rather than creating a
    second one - see routers/requests.py::_create_request. The permanent
    folder for a request is named after request_number when the request has
    one, falling back to request_id for legacy requests that don't.
    """

    __tablename__ = "requests"
    __table_args__ = (UniqueConstraint("owner_id", "request_number", name="uq_owner_request_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    request_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    request_type: Mapped[str] = mapped_column(String(50), default="")  # CDR, IMEI, Gateway
    # Ufone / Mobilink / Telenor / Zong. Supplied by the requester, never derived
    # from the number prefix: ported (MNP) numbers make the prefix unreliable.
    network: Mapped[str] = mapped_column(String(50), default="")
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

    # request_type / network / duration live per-number, not per-request: one
    # request_number (e.g. As-123460) can mix CDR, IMEI, NIC, FT ... rows, each
    # with its own network and duration (or none). The export groups on these.
    request_type: Mapped[str] = mapped_column(String(50), default="")
    network: Mapped[str] = mapped_column(String(50), default="")
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # A single entered number can fan out into several independently-tracked
    # records: a network-less IMEI becomes one row per operator, and a Telenor
    # CDR over 180 days becomes two date-window rows. `part` is the window index
    # (1 or 2) for that Telenor split, 0 for a normal single-window record.
    # date_from/date_to persist the window so it doesn't drift with today()
    # between request and response time: the export renders exactly this window
    # and the watcher attributes an incoming file to the window that contains
    # its date. Both are null for non-split rows.
    part: Mapped[int] = mapped_column(Integer, default=0)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)

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
