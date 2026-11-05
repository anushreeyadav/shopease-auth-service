"""Runs the 22 mandatory API test scenarios through the application, on in-memory SQLite."""

import pytest
from fastapi.testclient import TestClient

from app.database.connection import get_db
from app.main import app
from app.models.user_model import User
from tests.api_scenarios import SCENARIOS, ScenarioContext


@pytest.fixture
def context(db):
    def deactivate(email):
        db.query(User).filter_by(email=email).one().is_active = False
        db.commit()

    app.dependency_overrides[get_db] = lambda: db
    yield ScenarioContext(TestClient(app), "test", deactivate)
    app.dependency_overrides.clear()


def test_all_mandatory_scenarios_are_defined():
    assert [scenario.id for scenario in SCENARIOS] == [f"TC-{number:02d}" for number in range(1, 23)]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
def test_scenario(context, scenario):
    response = scenario.run(context)
    assert response.status_code == scenario.expected_status
    assert scenario.check(response)
