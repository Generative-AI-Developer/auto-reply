from .models import Request
from .schemas import RequestNumberOut, RequestOut, ResponseFileOut


def request_to_out(req: Request) -> RequestOut:
    return RequestOut(
        id=req.id,
        request_id=req.request_id,
        request_number=req.request_number,
        owner_user_id=req.owner.user_id if req.owner else "",
        numbers=[
            RequestNumberOut(
                id=i.id,
                value=i.value,
                status=i.status,
                request_type=i.request_type,
                network=i.network,
                duration_days=i.duration_days,
                part=i.part or 0,
                date_from=i.date_from,
                date_to=i.date_to,
                files=[ResponseFileOut.model_validate(f) for f in i.files],
            )
            for i in req.identifiers
        ],
        request_type=req.request_type,
        network=req.network,
        duration_days=req.duration_days,
        case_officer=req.case_officer,
        justification=req.justification,
        request_date=req.request_date,
        created_at=req.created_at,
    )
