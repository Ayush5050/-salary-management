from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.domain.compensation import Compensation, total_comp_usd_fx_scaled
from app.models import Country, Currency, Employee
from tests.conftest import SEEDED_EMPLOYEE_COUNT


class TestSeededContents:
    def test_loads_the_requested_number_of_employees(self, seeded_session):
        count = seeded_session.scalar(select(func.count()).select_from(Employee))
        assert count == SEEDED_EMPLOYEE_COUNT

    def test_loads_the_reference_tables(self, seeded_session):
        assert seeded_session.scalar(select(func.count()).select_from(Currency)) == 9
        assert seeded_session.scalar(select(func.count()).select_from(Country)) == 10

    def test_every_employee_resolves_to_a_country_and_currency(self, seeded_session):
        orphaned = seeded_session.scalar(
            select(func.count())
            .select_from(Employee)
            .outerjoin(Country, Employee.country_code == Country.code)
            .outerjoin(Currency, Employee.currency_code == Currency.code)
            .where((Country.code.is_(None)) | (Currency.code.is_(None)))
        )
        assert orphaned == 0

    def test_most_employees_have_a_reporting_line(self, seeded_session):
        managed = seeded_session.scalar(
            select(func.count()).select_from(Employee).where(Employee.manager_id.is_not(None))
        )
        assert managed > SEEDED_EMPLOYEE_COUNT * 0.8


class TestDerivedColumnInvariant:
    """The denormalised USD column is the one place stored state can go stale.

    Every read path trusts it, so it is checked against a recomputation from the
    employee's own salary and their currency's rate.
    """

    def test_stored_usd_total_matches_recomputation_for_every_employee(self, seeded_session):
        rows = seeded_session.execute(
            select(
                Employee.base_salary_minor,
                Employee.bonus_minor,
                Employee.currency_code,
                Employee.total_comp_usd_fx_scaled,
                Currency.usd_rate_scaled,
            ).join(Currency, Employee.currency_code == Currency.code)
        ).all()

        assert len(rows) == SEEDED_EMPLOYEE_COUNT
        for base, bonus, currency_code, stored, rate in rows:
            expected = total_comp_usd_fx_scaled(
                Compensation(
                    base_salary_minor=base, bonus_minor=bonus, currency_code=currency_code
                ),
                rate,
            )
            assert stored == expected


class TestSchemaConstraints:
    def test_a_negative_salary_is_rejected_by_the_database(self, seeded_session):
        """Defence in depth: the API validates too, but the constraint means no
        code path — including a future bulk import — can persist nonsense."""
        employee = seeded_session.scalar(select(Employee).limit(1))
        employee.base_salary_minor = -1

        try:
            seeded_session.flush()
        except IntegrityError:
            seeded_session.rollback()
        else:
            seeded_session.rollback()
            raise AssertionError("expected the check constraint to reject a negative salary")

    def test_an_unknown_manager_is_rejected_by_the_database(self, seeded_session):
        employee = seeded_session.scalar(select(Employee).limit(1))
        employee.manager_id = 10**9

        try:
            seeded_session.flush()
        except IntegrityError:
            seeded_session.rollback()
        else:
            seeded_session.rollback()
            raise AssertionError("expected the foreign key to reject an unknown manager")


class TestReproducibility:
    def test_seeding_twice_produces_identical_data(self, engine, seeded_session):
        """Guards the promise that the deployed demo and a local run agree."""
        first = seeded_session.execute(
            select(Employee.employee_code, Employee.total_comp_usd_fx_scaled).order_by(Employee.id)
        ).all()

        from sqlalchemy.orm import Session

        from app.models import Base
        from app.seed.run import seed_database
        from tests.conftest import SEEDED_RANDOM_SEED

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with Session(engine) as second_session:
            seed_database(second_session, SEEDED_EMPLOYEE_COUNT, SEEDED_RANDOM_SEED)
            second = second_session.execute(
                select(Employee.employee_code, Employee.total_comp_usd_fx_scaled).order_by(
                    Employee.id
                )
            ).all()

        assert first == second
