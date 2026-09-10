"""Dashboard endpoints.

Each takes the same filter query parameters as the employee list, so the client
can hold one filter state and point it at every panel on the page.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import EmployeeFiltersDep
from app.db import get_session
from app.domain.enums import DEPARTMENT_LABELS, LEVEL_LABELS, BreakdownDimension
from app.repositories import analytics as repository
from app.repositories.reference import country_names
from app.schemas import BandResponse, BreakdownGroup, StatsResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

SessionDep = Annotated[Session, Depends(get_session)]


def _labeller(session: Session, dimension: BreakdownDimension) -> dict[str, str]:
    """Display names for a dimension's keys.

    Country names come from the database; departments and levels are controlled
    vocabularies, so their labels are in the domain. Either way the analytics
    repository stays free of presentation concerns.
    """
    if dimension is BreakdownDimension.COUNTRY:
        return country_names(session)
    if dimension is BreakdownDimension.DEPARTMENT:
        return {key.value: label for key, label in DEPARTMENT_LABELS.items()}
    return {key.value: label for key, label in LEVEL_LABELS.items()}


@router.get("/summary", response_model=StatsResponse)
def summary(session: SessionDep, filters: EmployeeFiltersDep) -> StatsResponse:
    return StatsResponse.of(repository.compensation_summary(session, filters))


@router.get("/breakdown", response_model=list[BreakdownGroup])
def breakdown(
    session: SessionDep,
    filters: EmployeeFiltersDep,
    dimension: Annotated[BreakdownDimension, Query()],
) -> list[BreakdownGroup]:
    labels = _labeller(session, dimension)
    return [
        BreakdownGroup(
            key=row.key,
            label=labels.get(row.key, row.key),
            stats=StatsResponse.of(row.stats),
        )
        for row in repository.compensation_breakdown(session, filters, dimension)
    ]


@router.get("/distribution", response_model=list[BandResponse])
def distribution(session: SessionDep, filters: EmployeeFiltersDep) -> list[BandResponse]:
    return [BandResponse.of(band) for band in repository.salary_distribution(session, filters)]
