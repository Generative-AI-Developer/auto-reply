from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..deps import get_current_user, get_db, require_admin
from ..models import Request, RequestIdentifier, Role, Status, User
from ..schemas import ImportResult, RequestCreate, RequestOut, StatusUpdate
from ..serializers import request_to_out
from ..services.excel import parse_excel
from ..services.parsers import normalize_number
from ..services.ws_manager import manager

router = APIRouter(prefix="/requests", tags=["requests"])
settings = get_settings()


def _create_request(db: Session, owner: User, payload: RequestCreate) -> Request:
    numbers = [normalize_number(n) for n in payload.numbers if normalize_number(n)]
    if not numbers:
        raise HTTPException(status_code=422, detail="At least one number is required")

    request_number = payload.request_number.strip()
    if not request_number:
        raise HTTPException(status_code=422, detail="Request Number is required")

    # Same requester submitting the same Request Number again adds to that
    # existing request (one request_id) instead of creating a duplicate.
    req = db.scalar(
        select(Request).where(Request.owner_id == owner.id, Request.request_number == request_number)
    )
    if req is None:
        req = Request(
            request_id=f"tmp-{uuid4().hex}",
            owner_id=owner.id,
            request_number=request_number,
            request_type=payload.request_type,
            duration_days=payload.duration_days,
            case_officer=payload.case_officer,
            justification=payload.justification,
            request_date=date.today(),
        )
        db.add(req)
        db.flush()  # assigns req.id
        req.request_id = f"REQ-{req.id:05d}"

    existing_values = {ident.value for ident in req.identifiers}
    for value in dict.fromkeys(numbers):  # de-dupe, preserve order
        if value not in existing_values:
            db.add(RequestIdentifier(request_id=req.id, value=value, status=Status.PENDING))

    # Permanent per-request folder inside the user's permanent folder, ready to
    # receive matched response files: main/<user_id>/<request_number>/ (falls
    # back to request_id, unreachable here since request_number is always set
    # on a request created through this function).
    folder_name = req.request_number or req.request_id
    (Path(settings.main_dir) / owner.user_id / folder_name).mkdir(parents=True, exist_ok=True)
    return req


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = _create_request(db, user, payload)
    db.commit()
    db.refresh(req)
    out = request_to_out(req)
    manager.broadcast_threadsafe({"event": "request_created", "request_id": req.request_id})
    return out


@router.post("/import", response_model=ImportResult)
async def import_requests(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=422, detail="Please upload an .xlsx file")

    rows, errors = parse_excel(await file.read())
    created = 0
    created_ids: list[str] = []
    for row in rows:
        try:
            req = _create_request(db, user, row)
            db.flush()
            created_ids.append(req.request_id)
            created += 1
        except HTTPException as e:
            errors.append(str(e.detail))
    db.commit()

    for rid in created_ids:
        manager.broadcast_threadsafe({"event": "request_created", "request_id": rid})
    return ImportResult(created=created, failed=len(errors), errors=errors)


@router.get("", response_model=list[RequestOut])
def list_requests(
    q: str | None = None,
    status_filter: str | None = None,
    owner: str | None = None,
    request_date: date | None = None,
    case_officer: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Users see their own requests; admins see all. `q` searches Request ID + any number.

    `status_filter` matches requests that have AT LEAST ONE number in that status
    (status is tracked per-number, not per-request).
    """
    stmt = (
        select(Request)
        .options(
            selectinload(Request.identifiers).selectinload(RequestIdentifier.files),
            selectinload(Request.owner),
        )
        .order_by(Request.created_at.desc())
    )

    if user.role != Role.ADMIN:
        stmt = stmt.where(Request.owner_id == user.id)
    elif owner:
        stmt = stmt.join(User, User.id == Request.owner_id).where(User.user_id == owner)

    if q:
        like = f"%{q.strip()}%"
        number_match = exists().where(
            (RequestIdentifier.request_id == Request.id) & (RequestIdentifier.value.ilike(like))
        )
        stmt = stmt.where(or_(Request.request_id.ilike(like), number_match))

    if status_filter:
        status_match = exists().where(
            (RequestIdentifier.request_id == Request.id) & (RequestIdentifier.status == status_filter)
        )
        stmt = stmt.where(status_match)
    if request_date:
        stmt = stmt.where(Request.request_date == request_date)
    if case_officer:
        stmt = stmt.where(Request.case_officer.ilike(f"%{case_officer}%"))

    return [request_to_out(r) for r in db.scalars(stmt).unique().all()]


@router.get("/{request_id}", response_model=RequestOut)
def get_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.scalar(select(Request).where(Request.request_id == request_id))
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if user.role != Role.ADMIN and req.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your request")
    return request_to_out(req)


@router.patch("/{request_id}/numbers/{identifier_id}/status", response_model=RequestOut)
def update_number_status(
    request_id: str,
    identifier_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Operator: manually set one number's status to Awaited / No Data Found
    (Sent stays watcher-driven). Status is per-number, so this never affects
    the other numbers on the same request."""
    if not payload.is_valid_manual():
        raise HTTPException(
            status_code=422,
            detail=f"Status must be one of {list(Status.MANUAL)}",
        )
    req = db.scalar(select(Request).where(Request.request_id == request_id))
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    ident = next((i for i in req.identifiers if i.id == identifier_id), None)
    if ident is None:
        raise HTTPException(status_code=404, detail="Number not found on this request")

    ident.status = payload.status
    db.commit()
    db.refresh(req)
    manager.broadcast_threadsafe(
        {
            "event": "status_changed",
            "request_id": req.request_id,
            "number": ident.value,
            "status": ident.status,
        }
    )
    return request_to_out(req)
