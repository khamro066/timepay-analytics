from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.services.analytics_service import (
    get_all_employees_ranking,
    get_company_daily_breakdown,
    get_daily_company_stats,
    get_day_of_week_stats,
    get_department_summary,
    get_employee_summary,
    get_latest_attendance_date,
    get_lateness_distribution,
    get_schedule_matrix,
)

router = APIRouter(prefix="/api", tags=["analytics"], dependencies=[Depends(get_current_user)])


@router.get("/employees/{employee_id}/summary")
def employee_summary(employee_id: int, date_from: str = Query(...), date_to: str = Query(...)):
    return get_employee_summary(employee_id, date_from, date_to)


@router.get("/ranking")
def ranking(
    date_from: str = Query(...),
    date_to: str = Query(...),
    department: str | None = Query(None),
    include_archived: bool = Query(False),
):
    return get_all_employees_ranking(date_from, date_to, department, include_archived)


@router.get("/departments/summary")
def department_summary(date_from: str = Query(...), date_to: str = Query(...), include_archived: bool = Query(False)):
    return get_department_summary(date_from, date_to, include_archived)


@router.get("/company/daily-stats")
def daily_stats(date: str = Query(...), department: str | None = Query(None)):
    return get_daily_company_stats(date, department)


@router.get("/company/daily-breakdown")
def daily_breakdown(date: str = Query(...), department: str | None = Query(None)):
    return get_company_daily_breakdown(date, department)


@router.get("/company/latest-data-date")
def latest_data_date():
    return {"date": get_latest_attendance_date()}


@router.get("/lateness-distribution")
def lateness_distribution(date_from: str = Query(...), date_to: str = Query(...), department: str | None = Query(None)):
    return get_lateness_distribution(date_from, date_to, department)


@router.get("/day-of-week-stats")
def day_of_week_stats(date_from: str = Query(...), date_to: str = Query(...), department: str | None = Query(None)):
    return get_day_of_week_stats(date_from, date_to, department)


SCHEDULE_MATRIX_MAX_DAYS = 366


@router.get("/schedule-matrix")
def schedule_matrix(
    date_from: str = Query(...),
    date_to: str = Query(...),
    department: str | None = Query(None),
    include_archived: bool = Query(False),
):
    # One column per calendar day per employee, so guard against an
    # accidentally huge range before building the grid.
    try:
        span_days = (datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")).days
    except ValueError:
        raise HTTPException(status_code=422, detail="date_from and date_to must be YYYY-MM-DD")
    if span_days < 0:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    if span_days + 1 > SCHEDULE_MATRIX_MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"date range must be at most {SCHEDULE_MATRIX_MAX_DAYS} days")

    return get_schedule_matrix(date_from, date_to, department, include_archived)
