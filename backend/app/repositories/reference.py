"""Reference data reads.

Feeds the filter panel's dropdowns and supplies the human labels the analytics
repository deliberately leaves off its rows.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Country, Currency


def list_countries(session: Session) -> list[Country]:
    return list(session.scalars(select(Country).order_by(Country.name)).all())


def list_currencies(session: Session) -> list[Currency]:
    return list(session.scalars(select(Currency).order_by(Currency.code)).all())


def country_names(session: Session) -> dict[str, str]:
    """Country code to display name, for labelling a breakdown."""
    return {code: name for code, name in session.execute(select(Country.code, Country.name))}
