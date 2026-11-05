# Day 1 Progress Report

**Date:** 4 November 2026
**Name:** Anushree Yadav
**Status:** Completed

## Planned tasks

- [x] Create the Authentication Microservice project structure
- [x] Configure dependencies and secure environment settings
- [x] Implement the MySQL database layer and user model
- [x] Configure Alembic migrations
- [x] Implement password security and JWT
- [x] Implement the registration and login APIs
- [x] Write automated tests and API documentation

## Completed work

- **Project structure:** created the `shopease-auth-service` FastAPI project, with routing, business logic, models, schemas, database, and security in separate folders. Added Docker and Docker Compose setup.
- **Configuration:** pinned all dependencies for Python 3.11 and moved sensitive settings into environment variables. The service refuses to start with missing, too-short, or placeholder secrets.
- **Database:** implemented the SQLAlchemy engine, sessions, and `get_db()` dependency, plus the `users` table for the `shopease_auth_db` database. Added a database connectivity check at `GET /health/db`.
- **Migrations:** configured Alembic to read its connection from the application settings, with no credentials in `alembic.ini`. Created two migrations: one creates the `users` table, and one sets the default role to `USER`.
- **Security:** implemented bcrypt password hashing and verification, password strength rules, JWT creation and validation, and reusable route dependencies. Protected routes check the user's current status in the database on each request.
- **Registration and login:** implemented `POST /api/auth/register` and `POST /api/auth/login`, with validation, duplicate email prevention, generic login errors, and a consistent error format.
- **Documentation:** wrote the API documentation, database schema, JWT authentication flow, and environment variable reference.

The code is local and has not been pushed to GitHub yet.

## Files created or changed

| File | Change |
| --- | --- |
| `app/main.py`, `app/exception_handlers.py` | Created the application and consistent error responses |
| `app/core/config.py` | Added MySQL and JWT settings with validation |
| `app/core/security.py` | Added password, token, and route authentication functions |
| `app/core/email_utils.py` | Added email normalization |
| `app/database/connection.py` | Added the engine, sessions, base class, and `get_db()` |
| `app/models/user_model.py` | Added the `User` model |
| `app/schemas/auth_schema.py` | Added request and response schemas |
| `app/services/auth_service.py` | Added registration and login logic |
| `app/routers/auth_routes.py` | Added the registration and login endpoints |
| `alembic/`, `alembic.ini` | Added the migration setup and two migrations |
| `tests/`, `pytest.ini` | Added automated tests |
| `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitignore` | Added container and ignore rules |
| `requirements.txt`, `.env`, `.env.example` | Added pinned dependencies, local secrets, and placeholder values |
| `README.md`, `DELIVERABELS/` | Added setup instructions and project documentation |

## Testing and results

| Check | Command or method | Result |
| --- | --- | --- |
| Automated tests | `python -m pytest` | 155 passed, with 1 deprecation warning |
| Test effectiveness | Deliberately broke the code in 28 ways | All caught by the tests, after 2 test gaps were found and closed |
| Dependency conflicts | `pip check` | Passed |
| Container health | `docker compose up --build` | API and MySQL both healthy |
| Migrations on MySQL 8.4.11 | `alembic upgrade head`, `alembic downgrade -1`, `alembic check` | Passed. Upgrading and downgrading both worked, and the models match the database. |
| Registration and login over HTTP against MySQL | One-off script, 16 checks | All passed |
| 8 simultaneous registrations with one email | One-off script | 1 succeeded and 7 returned 409 |
| Login with the database stopped | Stopped MySQL and sent a login request | Returned 503 |
| Secrets in API container logs | Searched for passwords, hashes, tokens, and secrets | None found |
| Known vulnerabilities | `pip-audit -r requirements.txt` | 3 findings across `python-jose` and `ecdsa`, described below |

The MySQL tests used a temporary container, which was removed afterwards. The dependency audit last ran before the authentication code was added; the dependencies have not changed since then.

## Screenshots

None were captured on this day. Evidence screenshots were captured on 5 November 2026, and are in the [screenshots folder](screenshots/README.md).

## Issues and resolutions

| Issue | Resolution |
| --- | --- |
| Passlib 1.7.4 is not compatible with newer `bcrypt` releases | Pinned `bcrypt` to 4.0.1. Hashing and verification passed with no warnings. |
| bcrypt ignores anything after 72 bytes of a password | Passwords over 72 bytes are now rejected rather than cut short. |
| FastAPI's default validation errors include submitted values, which could return a rejected password | Added a custom format that returns only the field name and message. |
| Default role was first set to `customer`, but the requirement is `USER` | Changed the default and added a migration that also updates existing rows. |
| `python-jose` 3.5.0 has an advisory with no fixed release (CVE-2026-85394) | Open. Settings allow HMAC algorithms only, and token decoding accepts only the configured algorithm. |
| `ecdsa`, installed by `python-jose`, has an advisory with no planned fix (CVE-2024-23342; reported twice by the audit) | Accepted for now. This service does not use ECDSA signing. |
| Starlette warns that using `httpx` with its test client is deprecated | Open. Tests still run, but `httpx2` will be needed in a future upgrade. |
| Port 8001 is also used by the root ShopEase stack | Made the host port configurable with `AUTH_SERVICE_HOST_PORT`. |

## Plan for tomorrow

- Capture evidence screenshots for the completed work.
- Continue with the remaining Auth Service work.
