import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import create_database_engine
from app.models import Base
from app.seed.run import seed_database

SEEDED_EMPLOYEE_COUNT = 250
"""Population size for database-backed tests.

Large enough to exercise grouping, pagination and both median parities; small
enough that the whole suite stays well under a second. Correctness of the
queries does not depend on scale — performance does, and that is measured
separately against the full 10,000 rather than asserted in a unit test.
"""

SEEDED_RANDOM_SEED = 7


@pytest.fixture
def engine() -> Engine:
    """A fresh in-memory database per test.

    Built through the same factory the application uses, so that pragmas —
    foreign key enforcement in particular — are identical in tests and in
    production. ``StaticPool`` keeps every connection pointed at the same
    in-memory database; without it each pooled connection would get its own
    empty one.
    """
    memory_engine = create_database_engine("sqlite://", echo=False, poolclass=StaticPool)
    Base.metadata.create_all(memory_engine)
    return memory_engine


@pytest.fixture
def session(engine: Engine) -> Session:
    with Session(engine) as open_session:
        yield open_session


@pytest.fixture
def seeded_session(session: Session) -> Session:
    seed_database(session, SEEDED_EMPLOYEE_COUNT, SEEDED_RANDOM_SEED)
    return session
