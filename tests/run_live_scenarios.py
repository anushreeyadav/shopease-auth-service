"""Runs the 22 mandatory API test scenarios over HTTP against a running service and MySQL.

Start the stack, then run this from the project root:

    docker compose up -d --build --wait
    python -m tests.run_live_scenarios

It prints the results as Markdown tables and exits with 1 if any scenario fails. Settings come from
.env: it needs the JWT secret to sign an expired token, and MySQL access to deactivate a user. Actual
results are built from selected response fields, so tokens are never printed. The test users are
deleted afterwards.
"""

import argparse
import sys
import time

import httpx
from sqlalchemy import delete, update

from app.database.connection import SessionLocal
from app.models.user_model import User
from tests.api_scenarios import SCENARIOS, ScenarioContext

HEADER = (
    "| ID | Endpoint | Request | Expected status | Actual status | Expected result | Actual result | Result |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |"
)


def deactivate(email: str) -> None:
    with SessionLocal() as session:
        session.execute(update(User).where(User.email == email).values(is_active=False))
        session.commit()


def delete_test_users(run_id: str) -> None:
    with SessionLocal() as session:
        session.execute(delete(User).where(User.email.like(f"tc%.{run_id}@example.com")))
        session.commit()


def describe(response) -> str:
    """Summarize a response. Token values are left out, and only field names are listed for errors."""
    body = response.json()
    if "errors" in body:
        fields = ", ".join(f"`{error['field']}`" for error in body["errors"])
        return f"`{body['detail']}` on {fields}"
    if "detail" in body:
        return f"`{body['detail']}`"
    if "access_token" in body:
        return f"`{body['message']}`. Token returned (value not recorded). Role `{body['user']['role']}`."
    if "valid" in body:
        return f"`valid: {str(body['valid']).lower()}`, with fields {', '.join(sorted(body['user']))}"
    if "user" in body:
        return f"`{body['message']}`. Role `{body['user']['role']}`, active `{str(body['user']['is_active']).lower()}`."
    if "message" in body:
        return f"`{body['message']}`"
    return f"Profile returned, with fields {', '.join(sorted(body))}"


def run_scenario(scenario, context) -> tuple[str, str, bool]:
    try:
        response = scenario.run(context)
        passed = response.status_code == scenario.expected_status and scenario.check(response)
        return str(response.status_code), describe(response), passed
    except Exception as exc:  # A scenario that cannot finish is recorded as a failure, not skipped.
        return "None", f"Not completed: {type(exc).__name__}", False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    arguments = parser.parse_args()

    run_id = str(int(time.time()))
    context = ScenarioContext(httpx.Client(base_url=arguments.url, timeout=20), run_id, deactivate)
    group, passed_count = None, 0
    try:
        for scenario in SCENARIOS:
            if scenario.group != group:
                group = scenario.group
                print(f"\n### {group}\n\n{HEADER}")
            actual_status, actual_result, passed = run_scenario(scenario, context)
            passed_count += passed
            print(
                f"| {scenario.id} | `{scenario.endpoint}` | {scenario.request} | {scenario.expected_status} "
                f"| {actual_status} | {scenario.expected_result} | {actual_result} | {'PASS' if passed else 'FAIL'} |"
            )
    finally:
        delete_test_users(run_id)
    print(f"\n{passed_count} of {len(SCENARIOS)} scenarios passed.")
    return 0 if passed_count == len(SCENARIOS) else 1


if __name__ == "__main__":
    sys.exit(main())
