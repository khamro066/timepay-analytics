from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.services.analytics_service import (
    get_all_employees_ranking,
    get_daily_company_stats,
    get_day_of_week_stats,
    get_department_summary,
    get_employee_summary,
    get_lateness_distribution,
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
def daily_stats(date: str = Query(...)):
    return get_daily_company_stats(date)


@router.get("/lateness-distribution")
def lateness_distribution(date_from: str = Query(...), date_to: str = Query(...), department: str | None = Query(None)):
    return get_lateness_distribution(date_from, date_to, department)


@router.get("/day-of-week-stats")
def day_of_week_stats(date_from: str = Query(...), date_to: str = Query(...), department: str | None = Query(None)):
    return get_day_of_week_stats(date_from, date_to, department)
