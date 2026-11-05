"""The 22 mandatory API test scenarios, defined once and run in two ways:

- tests/test_api_scenarios.py runs them through the application on in-memory SQLite.
- tests/run_live_scenarios.py runs them over HTTP against a running service and MySQL.

Each scenario creates its own user, so that scenarios do not depend on one another.
All credentials are dummy values.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from app.core.security import create_access_token

PASSWORD = "Test!Pass123"
NEW_PASSWORD = "New!Pass456"
WRONG_PASSWORD = "Wrong!Pass789"
WEAK_PASSWORD = "weak"

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
ME = "/api/auth/me"
VERIFY = "/api/auth/verify-token"
CHANGE_PASSWORD = "/api/auth/change-password"

INVALID_TOKEN = "not-a-valid-token"
USER_FIELDS = {"id", "full_name", "email", "role", "is_active"}
UNAUTHORIZED = {"detail": "Could not validate credentials"}
SCENARIOS = []


class ScenarioContext:
    """Connects the scenarios to a client, and to a way of deactivating a user directly."""

    def __init__(self, client, run_id: str, deactivate: Callable[[str], None]):
        self.client = client
        self.run_id = run_id
        self.deactivate = deactivate

    def email(self, scenario_id: str) -> str:
        return f"{scenario_id.lower().replace('-', '')}.{self.run_id}@example.com"

    def registration(self, scenario_id: str, **overrides) -> dict:
        return {
            "full_name": "Test User",
            "email": self.email(scenario_id),
            "password": PASSWORD,
            "confirm_password": PASSWORD,
            **overrides,
        }

    def register(self, scenario_id: str) -> dict:
        response = self.client.post(REGISTER, json=self.registration(scenario_id))
        if response.status_code != 201:
            raise RuntimeError(f"Setup failed: registration returned {response.status_code}")
        return response.json()["user"]

    def login(self, scenario_id: str, password: str = PASSWORD):
        return self.client.post(LOGIN, json={"email": self.email(scenario_id), "password": password})

    def signed_in(self, scenario_id: str) -> dict:
        """Register and log in a new user, and return the Authorization header."""
        self.register(scenario_id)
        response = self.login(scenario_id)
        if response.status_code != 200:
            raise RuntimeError(f"Setup failed: login returned {response.status_code}")
        return bearer(response.json()["access_token"])

    def change_password(self, headers: dict | None, current=PASSWORD, new=NEW_PASSWORD):
        body = {"current_password": current, "new_password": new, "confirm_new_password": new}
        return self.client.post(CHANGE_PASSWORD, json=body, headers=headers or {})

    def changed_password(self, scenario_id: str) -> None:
        """Register a user and change their password from PASSWORD to NEW_PASSWORD."""
        response = self.change_password(self.signed_in(scenario_id))
        if response.status_code != 200:
            raise RuntimeError(f"Setup failed: password change returned {response.status_code}")


@dataclass(frozen=True)
class Scenario:
    id: str
    group: str
    endpoint: str
    request: str
    expected_status: int
    expected_result: str
    run: Callable[[ScenarioContext], object]
    check: Callable[[object], bool]


def scenario(id, group, endpoint, request, expected_status, expected_result, check):
    def add(run):
        SCENARIOS.append(Scenario(id, group, endpoint, request, expected_status, expected_result, run, check))
        return run
    return add


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def error_fields(response) -> set[str]:
    return {error["field"] for error in response.json()["errors"]}


def is_unauthorized(response) -> bool:
    return response.json() == UNAUTHORIZED and response.headers["WWW-Authenticate"] == "Bearer"


def is_safe_user(user: dict, scenario_id: str) -> bool:
    return set(user) == USER_FIELDS and user["email"].startswith(f"{scenario_id}.") and user["is_active"] is True


def is_login_success(response, scenario_id: str) -> bool:
    body = response.json()
    return (
        set(body) == {"message", "access_token", "token_type", "user"}
        and body["token_type"] == "bearer"
        and bool(body["access_token"])
        and is_safe_user(body["user"], scenario_id)
    )


def is_failed_login(response) -> bool:
    return response.json() == {"detail": "Invalid email or password"}


# Registration


@scenario(
    "TC-01", "Registration", f"POST {REGISTER}",
    f"New email `tc01.<run>@example.com`, password and confirm_password `{PASSWORD}`",
    201, "The user is created with role USER and is active. No password data is returned.",
    lambda r: r.json()["message"] == "User registered successfully"
    and is_safe_user(r.json()["user"], "tc01")
    and r.json()["user"]["role"] == "USER"
    and "password" not in r.text,
)
def _tc01(ctx):
    return ctx.client.post(REGISTER, json=ctx.registration("TC-01"))


@scenario(
    "TC-02", "Registration", f"POST {REGISTER}",
    "The same email, `tc02.<run>@example.com`, is registered a second time",
    409, "The request is rejected with `Email already registered`.",
    lambda r: r.json() == {"detail": "Email already registered"},
)
def _tc02(ctx):
    ctx.register("TC-02")
    return ctx.client.post(REGISTER, json=ctx.registration("TC-02"))


@scenario(
    "TC-03", "Registration", f"POST {REGISTER}",
    "Email `not-an-email`, with otherwise valid fields",
    422, "The request is rejected with a validation error on `email`.",
    lambda r: error_fields(r) == {"email"},
)
def _tc03(ctx):
    return ctx.client.post(REGISTER, json=ctx.registration("TC-03", email="not-an-email"))


@scenario(
    "TC-04", "Registration", f"POST {REGISTER}",
    "Only `email` is sent. `full_name`, `password`, and `confirm_password` are missing.",
    422, "The request is rejected with a validation error on each missing field.",
    lambda r: error_fields(r) == {"full_name", "password", "confirm_password"},
)
def _tc04(ctx):
    return ctx.client.post(REGISTER, json={"email": ctx.email("TC-04")})


@scenario(
    "TC-05", "Registration", f"POST {REGISTER}",
    f"password `{PASSWORD}`, confirm_password `{WRONG_PASSWORD}`",
    422, "The request is rejected with `Passwords do not match` on `confirm_password`.",
    lambda r: r.json()["errors"] == [{"field": "confirm_password", "message": "Passwords do not match"}],
)
def _tc05(ctx):
    return ctx.client.post(REGISTER, json=ctx.registration("TC-05", confirm_password=WRONG_PASSWORD))


@scenario(
    "TC-06", "Registration", f"POST {REGISTER}",
    f"password and confirm_password `{WEAK_PASSWORD}`",
    422, "The request is rejected with the unmet strength rules on `password`. The password is not echoed.",
    lambda r: error_fields(r) == {"password"}
    and "at least 8 characters" in r.json()["errors"][0]["message"]
    and f'"{WEAK_PASSWORD}"' not in r.text,
)
def _tc06(ctx):
    body = ctx.registration("TC-06", password=WEAK_PASSWORD, confirm_password=WEAK_PASSWORD)
    return ctx.client.post(REGISTER, json=body)


# Login


@scenario(
    "TC-07", "Login", f"POST {LOGIN}",
    f"Registered email `tc07.<run>@example.com`, password `{PASSWORD}`",
    200, "An access token and the user's profile are returned.",
    lambda r: is_login_success(r, "tc07"),
)
def _tc07(ctx):
    ctx.register("TC-07")
    return ctx.login("TC-07")


@scenario(
    "TC-08", "Login", f"POST {LOGIN}",
    f"Registered email `tc08.<run>@example.com`, password `{WRONG_PASSWORD}`",
    401, "The login is rejected with `Invalid email or password`. No token is returned.",
    is_failed_login,
)
def _tc08(ctx):
    ctx.register("TC-08")
    return ctx.login("TC-08", WRONG_PASSWORD)


@scenario(
    "TC-09", "Login", f"POST {LOGIN}",
    f"Unregistered email `tc09.<run>@example.com`, password `{PASSWORD}`",
    401, "The login gets the same rejection as a wrong password, so the email's existence is not revealed.",
    is_failed_login,
)
def _tc09(ctx):
    return ctx.login("TC-09")


@scenario(
    "TC-10", "Login", f"POST {LOGIN}",
    f"Email `tc10.<run>@example.com`, password `{PASSWORD}`. `is_active` was set to false in the database first.",
    403, "The login is rejected with `Inactive user`. No token is returned.",
    lambda r: r.json() == {"detail": "Inactive user"},
)
def _tc10(ctx):
    ctx.register("TC-10")
    ctx.deactivate(ctx.email("TC-10"))
    return ctx.login("TC-10")


# JWT authentication


@scenario(
    "TC-11", "JWT authentication", f"GET {ME}",
    "`Authorization: Bearer <token from login>`",
    200, "The user's profile is returned, with no password data.",
    lambda r: is_safe_user(r.json(), "tc11") and "password" not in r.text,
)
def _tc11(ctx):
    return ctx.client.get(ME, headers=ctx.signed_in("TC-11"))


@scenario(
    "TC-12", "JWT authentication", f"GET {ME}",
    "No `Authorization` header",
    401, "The request is rejected with `Could not validate credentials`.",
    is_unauthorized,
)
def _tc12(ctx):
    ctx.register("TC-12")  # An existing user, so that a bypass of the token check would return 200.
    return ctx.client.get(ME)


@scenario(
    "TC-13", "JWT authentication", f"GET {ME}",
    f"`Authorization: Bearer {INVALID_TOKEN}`",
    401, "The request is rejected with `Could not validate credentials`.",
    is_unauthorized,
)
def _tc13(ctx):
    ctx.register("TC-13")
    return ctx.client.get(ME, headers=bearer(INVALID_TOKEN))


@scenario(
    "TC-14", "JWT authentication", f"GET {ME}",
    "`Authorization: Bearer <correctly signed token that expired 1 second ago>`, for an existing user",
    401, "The request is rejected with `Could not validate credentials`.",
    is_unauthorized,
)
def _tc14(ctx):
    user = ctx.register("TC-14")
    expired = create_access_token(user["id"], user["role"], timedelta(seconds=-1))
    return ctx.client.get(ME, headers=bearer(expired))


@scenario(
    "TC-15", "JWT authentication", f"POST {VERIFY}",
    "`Authorization: Bearer <token from login>`",
    200, 'The response has `"valid": true` and the user\'s profile.',
    lambda r: r.json()["valid"] is True and is_safe_user(r.json()["user"], "tc15"),
)
def _tc15(ctx):
    return ctx.client.post(VERIFY, headers=ctx.signed_in("TC-15"))


@scenario(
    "TC-16", "JWT authentication", f"POST {VERIFY}",
    f"`Authorization: Bearer {INVALID_TOKEN}`",
    401, "The request is rejected with `Could not validate credentials`.",
    is_unauthorized,
)
def _tc16(ctx):
    ctx.register("TC-16")
    return ctx.client.post(VERIFY, headers=bearer(INVALID_TOKEN))


# Change password


@scenario(
    "TC-17", "Change password", f"POST {CHANGE_PASSWORD}",
    f"Bearer token, current_password `{PASSWORD}`, new_password and confirm_new_password `{NEW_PASSWORD}`",
    200, "The password is changed, and only a success message is returned.",
    lambda r: r.json() == {"message": "Password changed successfully"},
)
def _tc17(ctx):
    return ctx.change_password(ctx.signed_in("TC-17"))


@scenario(
    "TC-18", "Change password", f"POST {CHANGE_PASSWORD}",
    f"Bearer token, current_password `{WRONG_PASSWORD}`, new_password and confirm_new_password `{NEW_PASSWORD}`",
    400, "The change is rejected with `Current password is incorrect`.",
    lambda r: r.json() == {"detail": "Current password is incorrect"},
)
def _tc18(ctx):
    return ctx.change_password(ctx.signed_in("TC-18"), current=WRONG_PASSWORD)


@scenario(
    "TC-19", "Change password", f"POST {CHANGE_PASSWORD}",
    f"Bearer token, current_password `{PASSWORD}`, new_password and confirm_new_password `{WEAK_PASSWORD}`",
    422, "The change is rejected with the unmet strength rules on `new_password`.",
    lambda r: error_fields(r) == {"new_password"},
)
def _tc19(ctx):
    return ctx.change_password(ctx.signed_in("TC-19"), new=WEAK_PASSWORD)


@scenario(
    "TC-20", "Change password", f"POST {CHANGE_PASSWORD}",
    f"No `Authorization` header, current_password `{PASSWORD}`, new_password and confirm_new_password `{NEW_PASSWORD}`",
    401, "The request is rejected with `Could not validate credentials`.",
    is_unauthorized,
)
def _tc20(ctx):
    ctx.register("TC-20")
    return ctx.change_password(None)


@scenario(
    "TC-21", "Change password", f"POST {LOGIN}",
    f"After changing the password from `{PASSWORD}` to `{NEW_PASSWORD}`, log in with `{NEW_PASSWORD}`",
    200, "The login succeeds with the new password.",
    lambda r: is_login_success(r, "tc21"),
)
def _tc21(ctx):
    ctx.changed_password("TC-21")
    return ctx.login("TC-21", NEW_PASSWORD)


@scenario(
    "TC-22", "Change password", f"POST {LOGIN}",
    f"After changing the password from `{PASSWORD}` to `{NEW_PASSWORD}`, log in with `{PASSWORD}`",
    401, "The login is rejected with `Invalid email or password`.",
    is_failed_login,
)
def _tc22(ctx):
    ctx.changed_password("TC-22")
    return ctx.login("TC-22", PASSWORD)
