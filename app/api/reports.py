from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.services.report_service import build_report_pdf, build_report_workbook, get_report_rows

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


@router.get("")
def report_data(
    date_from: str = Query(...),
    date_to: str = Query(...),
    period_key: str = Query(...),
    include_archived: bool = Query(False),
):
    return get_report_rows(date_from, date_to, period_key, include_archived)


@router.get("/export")
def export_report(
    date_from: str = Query(...),
    date_to: str = Query(...),
    period_key: str = Query(...),
    department: str | None = Query(None),
    include_archived: bool = Query(False),
):
    buffer = build_report_workbook(date_from, date_to, period_key, include_archived, department)
    filename = f"hisobot_{date_from}_{date_to}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/pdf")
def export_report_pdf(
    date_from: str = Query(...),
    date_to: str = Query(...),
    period_key: str = Query(...),
    department: str | None = Query(None),
    include_archived: bool = Query(False),
):
    buffer = build_report_pdf(date_from, date_to, period_key, department, include_archived)
    filename = f"hisobot_{date_from}_{date_to}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
