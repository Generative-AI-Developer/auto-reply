"""Match incoming-file identifiers against stored requests.

Rule (per plan): a Pending request matches when ANY of its numbers is in the
incoming file's numbers AND its request_date equals the file's date. If the file
exposes no date, fall back to the oldest Pending request carrying the number.

TODO(confirm): the date fallback assumes incoming files usually carry a date in
their name/content. Revisit once real response files are available.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Request, RequestIdentifier, Status


def find_matches(db: Session, numbers: set[str], file_date: date | None) -> list[Request]:
    if not numbers:
        return []

    stmt = (
        select(Request)
        .join(RequestIdentifier, RequestIdentifier.request_id == Request.id)
        .where(
            RequestIdentifier.value.in_(numbers),
            Request.status == Status.PENDING,
        )
    )

    if file_date is not None:
        stmt = stmt.where(Request.request_date == file_date)
        return list(db.scalars(stmt).unique().all())

    # No date on the file: fall back to the oldest Pending request per matched number.
    candidates = list(db.scalars(stmt.order_by(Request.created_at.asc())).unique().all())
    seen_numbers: set[str] = set()
    chosen: list[Request] = []
    for req in candidates:
        req_numbers = {i.value for i in req.identifiers} & numbers
        # keep this request only if it introduces a number not already served
        if req_numbers - seen_numbers:
            chosen.append(req)
            seen_numbers |= req_numbers
    return chosen
