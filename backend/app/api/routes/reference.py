"""Reference data endpoint: one request that fills every dropdown."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.domain.enums import (
    DEPARTMENT_LABELS,
    EMPLOYMENT_TYPE_LABELS,
    LEVEL_LABELS,
    EmploymentStatus,
)
from app.repositories import reference as repository
from app.schemas import CountryOption, CurrencyOption, LabelledOption, ReferenceData

router = APIRouter(prefix="/reference", tags=["reference"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=ReferenceData)
def get_reference_data(session: SessionDep, settings: SettingsDep) -> ReferenceData:
    return ReferenceData(
        countries=[CountryOption.of(country) for country in repository.list_countries(session)],
        currencies=[
            CurrencyOption.of(currency) for currency in repository.list_currencies(session)
        ],
        departments=[
            LabelledOption(value=key.value, label=label) for key, label in DEPARTMENT_LABELS.items()
        ],
        levels=[
            LabelledOption(value=key.value, label=label) for key, label in LEVEL_LABELS.items()
        ],
        employment_types=[
            LabelledOption(value=key.value, label=label)
            for key, label in EMPLOYMENT_TYPE_LABELS.items()
        ],
        statuses=[
            LabelledOption(value=status.value, label=status.value.title())
            for status in EmploymentStatus
        ],
        base_currency=settings.base_currency,
    )
