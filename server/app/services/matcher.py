"""Match incoming-file identifiers against stored request numbers.

Rule (per plan): a Pending number matches when its value is in the incoming
file's numbers AND its parent request's request_date equals the file's date.
Status is tracked per-number, so a response for one number in a request never
affects the other numbers on that same request. If the file exposes no date,
fall back to the oldest Pending number with that value.

TODO(confirm): the date fallback assumes incoming files usually carry a date in
their name/content. Revisit once real response files are available.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Request, RequestIdentifier, Status


def find_matches(db: Session, numbers: set[str], file_date: date | None) -> list[RequestIdentifier]:
    if not numbers:
        return []

    stmt = (
        select(RequestIdentifier)
        .join(Request, Request.id == RequestIdentifier.request_id)
        .options(selectinload(RequestIdentifier.request).selectinload(Request.owner))
        .where(
            RequestIdentifier.value.in_(numbers),
            RequestIdentifier.status == Status.PENDING,
        )
    )

    if file_date is not None:
        stmt = stmt.where(Request.request_date == file_date)
        return list(db.scalars(stmt).all())

    # No date on the file: fall back to the oldest Pending identifier per value.
    candidates = list(db.scalars(stmt.order_by(Request.created_at.asc())).all())
    seen_values: set[str] = set()
    chosen: list[RequestIdentifier] = []
    for ident in candidates:
        if ident.value not in seen_values:
            chosen.append(ident)
            seen_values.add(ident.value)
    return chosen
