from .models import Request
from .schemas import RequestOut, ResponseFileOut


def request_to_out(req: Request) -> RequestOut:
    return RequestOut(
        id=req.id,
        request_id=req.request_id,
        owner_user_id=req.owner.user_id if req.owner else "",
        numbers=[i.value for i in req.identifiers],
        duration_days=req.duration_days,
        case_officer=req.case_officer,
        justification=req.justification,
        request_date=req.request_date,
        status=req.status,
        created_at=req.created_at,
        files=[ResponseFileOut.model_validate(f) for f in req.files],
    )
