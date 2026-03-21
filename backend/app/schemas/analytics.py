"""
Pydantic схемы для аналитики.
"""

from datetime import date, datetime

from pydantic import BaseModel


class StageCount(BaseModel):
    stage: str
    count: int


class AnalyticsOverview(BaseModel):
    """Общая статистика за период."""

    total_candidates: int
    new_this_week: int
    by_stage: list[StageCount]
    conversion_rate: float
    avg_time_in_stage: float  # дней


class FunnelStage(BaseModel):
    name: str
    count: int
    conversion_from_prev: float | None  # %
    avg_days: float | None


class AnalyticsFunnel(BaseModel):
    """Конверсионная воронка."""

    stages: list[FunnelStage]


class VacancyStats(BaseModel):
    vacancy_id: str
    vacancy_title: str
    total: int
    by_stage: list[StageCount]


class AnalyticsByVacancy(BaseModel):
    items: list[VacancyStats]
    total_vacancies: int


class UserStats(BaseModel):
    user_id: str
    full_name: str
    total: int
    active: int
    completed: int


class AnalyticsByResponsible(BaseModel):
    items: list[UserStats]


class DepartmentStats(BaseModel):
    department_id: str
    department_name: str
    total: int
    active: int
    completed: int


class AnalyticsByDepartment(BaseModel):
    items: list[DepartmentStats]


class ActivityDay(BaseModel):
    date: date
    messages_count: int
    changes_count: int
    total: int


class AnalyticsActivity(BaseModel):
    """Активность команды по дням."""

    items: list[ActivityDay]
    date_from: date
    date_to: date
