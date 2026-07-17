"""Match incoming-file identifiers against stored request numbers.

Rule: a Pending number matches when its last 10 digits appear anywhere in one
of the incoming file's numbers (or vice versa) - not necessarily aligned at
the end. Country codes / leading zeros / stray prefix-suffix digits mean the
shared core can land as a prefix, suffix, or in the middle of either value, so
this checks substring containment both ways rather than requiring the two
10-digit cores to be equal. Status is tracked per-number, so a response for
one number in a request never affects the other numbers on that same request.

Matching does not consider request_date: request_date records when the
request was submitted (always "today" at creation, see routers/requests.py),
not the date of the data being requested, so it isn't a signal for whether an
incoming file belongs to a given request.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Request, RequestIdentifier, Status

_CORE_LEN = 10


def _core(value: str) -> str:
    return value[-_CORE_LEN:] if len(value) >= _CORE_LEN else value


def _same_number(a: str, b: str) -> bool:
    return _core(a) in b or _core(b) in a


def find_matches(db: Session, numbers: set[str]) -> list[RequestIdentifier]:
    if not numbers:
        return []

    stmt = (
        select(RequestIdentifier)
        .join(Request, Request.id == RequestIdentifier.request_id)
        .options(selectinload(RequestIdentifier.request).selectinload(Request.owner))
        .where(RequestIdentifier.status == Status.PENDING)
    )
    return [
        ident
        for ident in db.scalars(stmt).all()
        if any(_same_number(ident.value, n) for n in numbers)
    ]
