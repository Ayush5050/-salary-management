"""API tests.

These drive the real application through an ASGI transport with a seeded
in-memory database — no mocked repositories. Mocking the layer directly beneath
the routes would only prove the routes call what the test says they call; going
through to SQL is what catches a filter that never reaches the query or a
response field that no longer exists.
"""

from urllib.parse import parse_qsl

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db import get_session
from app.main import app
from tests.conftest import SEEDED_EMPLOYEE_COUNT


@pytest.fixture
def client(engine: Engine, seeded_session: Session) -> TestClient:
    """A client bound to the test database.

    The session dependency is overridden rather than the repositories, so every
    request exercises the same query path production uses.
    """

    def session_override():
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def valid_payload(**overrides) -> dict:
    body = {
        "employee_code": "ACME-90001",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada.lovelace@acme.example",
        "country_code": "GB",
        "department": "ENGINEERING",
        "job_title": "Principal Engineer",
        "level": "L5",
        "employment_type": "FULL_TIME",
        "status": "ACTIVE",
        "hire_date": "2024-03-01",
        "manager_id": None,
        "currency_code": "GBP",
        "base_salary_minor": 15_000_000,
        "bonus_minor": 2_000_000,
    }
    return body | overrides


class TestHealth:
    def test_reports_ok(self, client):
        assert client.get("/api/health").json() == {"status": "ok"}


class TestListEndpoint:
    def test_returns_a_page_and_the_full_total(self, client):
        body = client.get("/api/employees", params={"page_size": 5}).json()

        assert len(body["items"]) == 5
        assert body["meta"]["total"] == SEEDED_EMPLOYEE_COUNT
        assert body["meta"]["page"] == 1

    def test_rows_carry_display_labels_and_both_currencies(self, client):
        row = client.get("/api/employees", params={"page_size": 1}).json()["items"][0]

        assert row["country_name"]
        assert row["department_label"]
        assert row["currency_symbol"]
        assert row["total_comp_local_minor"] == row["base_salary_minor"] + row["bonus_minor"]
        assert row["total_comp_usd_minor"] > 0

    def test_repeated_query_parameters_filter_disjunctively(self, client):
        both = client.get(
            "/api/employees", params=[("country", "IN"), ("country", "DE"), ("page_size", 1)]
        ).json()
        india = client.get("/api/employees", params={"country": "IN", "page_size": 1}).json()
        germany = client.get("/api/employees", params={"country": "DE", "page_size": 1}).json()

        assert both["meta"]["total"] == india["meta"]["total"] + germany["meta"]["total"]

    def test_rejects_a_page_size_above_the_cap(self, client):
        response = client.get("/api/employees", params={"page_size": 5_000})

        assert response.status_code == 400
        assert "exceeds the maximum" in response.json()["detail"]

    def test_rejects_an_inverted_compensation_range(self, client):
        response = client.get(
            "/api/employees",
            params={"min_total_comp_usd_minor": 20_000_000, "max_total_comp_usd_minor": 1},
        )

        assert response.status_code == 400
        assert "exceeds maximum" in response.json()["detail"]

    def test_rejects_an_unknown_sort_field(self, client):
        assert client.get("/api/employees", params={"sort": "FAVOURITE_COLOUR"}).status_code == 422


class TestDetailEndpoint:
    def test_returns_the_employee_with_their_manager(self, client):
        listed = client.get("/api/employees", params={"page_size": 50}).json()["items"]
        detail = client.get(f"/api/employees/{listed[0]['id']}").json()

        assert detail["employee_code"] == listed[0]["employee_code"]
        assert "manager" in detail

    def test_missing_employee_is_a_404_naming_the_id(self, client):
        response = client.get("/api/employees/999999")

        assert response.status_code == 404
        assert response.json()["detail"] == "no employee with id 999999"
        assert response.json()["error"] == "EmployeeNotFoundError"


class TestWriteEndpoints:
    def test_creates_an_employee(self, client):
        response = client.post("/api/employees", json=valid_payload())

        assert response.status_code == 201
        assert response.json()["total_comp_usd_minor"] == 21_590_000

    def test_a_duplicate_email_is_a_409(self, client):
        existing = client.get("/api/employees", params={"page_size": 1}).json()["items"][0]
        response = client.post("/api/employees", json=valid_payload(email=existing["email"]))

        assert response.status_code == 409
        assert existing["employee_code"] in response.json()["detail"]

    def test_an_unknown_currency_is_a_422(self, client):
        response = client.post("/api/employees", json=valid_payload(currency_code="XXX"))

        assert response.status_code == 422
        assert response.json()["error"] == "UnknownReferenceError"

    def test_a_negative_salary_is_rejected_by_validation(self, client):
        response = client.post("/api/employees", json=valid_payload(base_salary_minor=-1))
        assert response.status_code == 422

    def test_a_malformed_email_is_rejected_by_validation(self, client):
        response = client.post("/api/employees", json=valid_payload(email="not-an-email"))
        assert response.status_code == 422

    def test_replacing_an_employee_updates_the_usd_total(self, client):
        created = client.post("/api/employees", json=valid_payload()).json()
        replaced = client.put(
            f"/api/employees/{created['id']}",
            json=valid_payload(base_salary_minor=20_000_000, bonus_minor=0),
        ).json()

        assert replaced["total_comp_usd_minor"] == 25_400_000

    def test_deactivating_an_employee_keeps_the_record(self, client):
        created = client.post("/api/employees", json=valid_payload()).json()
        response = client.patch(
            f"/api/employees/{created['id']}/status", json={"status": "INACTIVE"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "INACTIVE"
        assert client.get(f"/api/employees/{created['id']}").status_code == 200

    def test_there_is_no_delete_endpoint(self, client):
        """Compensation records are financial history."""
        created = client.post("/api/employees", json=valid_payload()).json()
        assert client.delete(f"/api/employees/{created['id']}").status_code == 405


class TestAnalyticsEndpoints:
    def test_summary_reports_every_headline_figure(self, client):
        body = client.get("/api/analytics/summary").json()

        assert body["headcount"] == SEEDED_EMPLOYEE_COUNT
        assert body["total_usd_minor"] > 0
        assert body["median_usd_minor"] is not None

    def test_summary_of_an_empty_selection_is_null_not_zero(self, client):
        body = client.get("/api/analytics/summary", params={"search": "nobody-matches-this"}).json()

        assert body["headcount"] == 0
        assert body["average_usd_minor"] is None
        assert body["median_usd_minor"] is None

    @pytest.mark.parametrize("dimension", ["COUNTRY", "DEPARTMENT", "LEVEL"])
    def test_breakdown_labels_every_group(self, client, dimension):
        groups = client.get("/api/analytics/breakdown", params={"dimension": dimension}).json()

        assert groups
        for group in groups:
            assert group["label"], f"group {group['key']} has no display label"
            assert group["stats"]["headcount"] > 0

    def test_country_breakdown_uses_country_names_not_codes(self, client):
        groups = client.get("/api/analytics/breakdown", params={"dimension": "COUNTRY"}).json()
        labels = {group["label"] for group in groups}

        assert "India" in labels or "United States" in labels

    def test_distribution_returns_every_band_in_order(self, client):
        bands = client.get("/api/analytics/distribution").json()

        assert bands[0]["lower_usd_minor"] == 0
        assert bands[-1]["upper_usd_minor"] is None
        assert sum(band["headcount"] for band in bands) == SEEDED_EMPLOYEE_COUNT

    def test_breakdown_requires_a_dimension(self, client):
        assert client.get("/api/analytics/breakdown").status_code == 422


class TestFilterConsistencyOverHttp:
    """The same query string must mean the same thing to every endpoint."""

    @pytest.mark.parametrize(
        "query",
        [
            {"status": "ACTIVE"},
            {"department": "ENGINEERING"},
            {"country": "IN", "status": "ACTIVE"},
            {"min_total_comp_usd_minor": 10_000_000},
        ],
    )
    def test_list_total_matches_summary_headcount(self, client, query):
        listed = client.get("/api/employees", params={**query, "page_size": 1}).json()
        summary = client.get("/api/analytics/summary", params=query).json()

        assert listed["meta"]["total"] == summary["headcount"]

    def test_breakdown_headcounts_sum_to_the_summary(self, client):
        query = {"status": "ACTIVE"}
        summary = client.get("/api/analytics/summary", params=query).json()
        groups = client.get(
            "/api/analytics/breakdown", params={**query, "dimension": "LEVEL"}
        ).json()

        assert sum(group["stats"]["headcount"] for group in groups) == summary["headcount"]


class TestReferenceEndpoint:
    def test_returns_everything_the_filter_panel_needs(self, client):
        body = client.get("/api/reference").json()

        assert len(body["countries"]) == 10
        assert len(body["currencies"]) == 9
        assert len(body["departments"]) == 10
        assert len(body["levels"]) == 8
        assert body["base_currency"] == "USD"

    def test_options_carry_human_labels(self, client):
        body = client.get("/api/reference").json()
        labels = {option["value"]: option["label"] for option in body["departments"]}

        assert labels["CUSTOMER_SUCCESS"] == "Customer Success"


class TestQuestionEndpoint:
    """The natural-language stretch feature.

    The endpoint returns the query string a question *means* rather than
    results, so these tests follow that string back through the ordinary
    endpoints — which is the property that keeps an answered question and a
    hand-built filter in agreement.
    """

    def ask(self, client, question: str) -> dict:
        response = client.post("/api/query", json={"question": question})
        assert response.status_code == 200, response.text
        return response.json()

    def test_translates_a_question_into_filters(self, client):
        body = self.ask(client, "what do we pay engineering in Germany?")
        params = dict(parse_qsl(body["query_string"]))

        assert params["department"] == "ENGINEERING"
        assert params["country"] == "DE"
        assert body["understood"] is True

    def test_echoes_an_interpretation_the_user_can_check(self, client):
        body = self.ask(client, "engineering in Germany over $100k by level")

        assert "Engineering" in body["interpretation"]
        assert "over $100,000" in body["interpretation"]
        assert body["dimension"] == "LEVEL"

    def test_the_returned_query_string_drives_the_real_endpoints(self, client):
        """The round trip: question → query string → the same views a person
        would have reached by hand, agreeing with each other."""
        body = self.ask(client, "engineering in India")
        query = body["query_string"]

        listed = client.get(f"/api/employees?{query}&page_size=1").json()
        summary = client.get(f"/api/analytics/summary?{query}").json()

        assert listed["meta"]["total"] == summary["headcount"]
        assert summary["headcount"] > 0

    def test_a_compensation_question_narrows_the_result(self, client):
        everyone = client.get("/api/analytics/summary?status=ACTIVE").json()
        body = self.ask(client, "who earns more than $200k")
        narrowed = client.get(f"/api/analytics/summary?{body['query_string']}").json()

        assert 0 < narrowed["headcount"] < everyone["headcount"]

    def test_reports_terms_it_could_not_interpret(self, client):
        body = self.ask(client, "engineering in Germany on Tuesdays")
        assert "tuesdays" in body["unrecognised_terms"]

    def test_rejects_an_empty_question(self, client):
        assert client.post("/api/query", json={"question": "   "}).status_code == 400

    def test_rejects_a_missing_question(self, client):
        assert client.post("/api/query", json={}).status_code == 422

    def test_a_question_can_only_become_a_filter_never_sql(self, client):
        """The guardrail. The parser emits a validated filter object, so a
        hostile question is at worst an ordinary bound search term."""
        body = self.ask(client, "'; DROP TABLE employees; --")
        client.get(f"/api/employees?{body['query_string']}")

        # The table is still there, and still complete.
        assert client.get("/api/employees?page_size=1").json()["meta"]["total"] == (
            SEEDED_EMPLOYEE_COUNT
        )
