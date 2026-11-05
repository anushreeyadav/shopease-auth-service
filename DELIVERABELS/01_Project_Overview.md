# Project Overview: ShopEase Auth Service

## Purpose

The Auth Service is an independent microservice responsible for authentication in the ShopEase platform. It has its own code, configuration, database, and container, and shares no files with the Product Service.

## Current status

User registration and login are implemented through `POST /api/auth/register` and `POST /api/auth/login`. They use the `shopease_auth_db` MySQL database, bcrypt password hashing, and JWT access tokens. `GET /api/auth/me`, `POST /api/auth/verify-token`, and `POST /api/auth/change-password` require a valid token and an active user. The service also exposes `/`, `/health`, and `/health/db`.

Implementation, testing on Docker with MySQL, and the evidence screenshots are complete. The commit and the GitHub push are pending. See the [final completion report](09_Final_Completion_Report.md).

## Technology

| Area | Choice |
| --- | --- |
| Language | Python 3.11 |
| Web framework | FastAPI 0.162, served by Uvicorn 0.54 |
| Validation and settings | Pydantic 2.14, pydantic-settings 2.16, python-dotenv 1.2, email-validator 2.3 |
| Database | MySQL 8.4, database `shopease_auth_db` |
| ORM, driver, and migrations | SQLAlchemy 2.1, PyMySQL 1.2, Alembic 1.20 |
| Password hashing | Passlib 1.7.4 with bcrypt 4.0.1 |
| Tokens | python-jose 3.5 with the cryptography backend |
| Testing | pytest 9.2, httpx 0.28 |
| Containers | Docker, Docker Compose |

## Architecture

Each layer has one responsibility, and requests flow from top to bottom:

| Layer | Location | Responsibility |
| --- | --- | --- |
| Routing | `app/routers/` | Receive HTTP requests and return responses |
| Schemas | `app/schemas/` | Validate request and response data |
| Business logic | `app/services/` | Apply authentication rules, independent of HTTP |
| Security | `app/core/security.py` | Hash passwords, handle tokens, and authenticate requests |
| Models | `app/models/` | Define database tables |
| Database | `app/database/` | Manage connections and sessions |
| Configuration | `app/core/config.py` | Load settings from the environment |

## Configuration and secrets

All sensitive settings come from environment variables or a local `.env` file. The README documents every variable.

- `.env` is excluded from Git and Docker images, and `.env.example` contains placeholders only.
- The service will not start if a required secret is missing, if the JWT secret is shorter than 32 characters, or if a secret still has its placeholder value.
- Secrets are masked in printed settings and logs, and they are not returned by the current API responses.

## Known dependency risks

| Package | Advisory | Fixed version | Current exposure |
| --- | --- | --- | --- |
| python-jose 3.5.0 | CVE-2026-85394, token forgery through algorithm confusion | None | Requires a service public key and unrestricted algorithms. This service allows HMAC algorithms only, and token decoding must always restrict the algorithm. |
| ecdsa 0.19.2, installed by python-jose | CVE-2024-23342, timing attack on P-256 signing | None planned | This service signs tokens with HMAC, not ECDSA. |

## Local addresses

| Component | Address |
| --- | --- |
| API | `http://127.0.0.1:8001` |
| API documentation | `http://127.0.0.1:8001/docs` |
| MySQL | `127.0.0.1:3308` |

## Deliverables

| File | Content |
| --- | --- |
| `01_Project_Overview.md` | This overview |
| `02_Day_1_Progress.md` | Day 1 progress report |
| `03_Day_2_Progress.md` | Day 2 progress report |
| `04_API_Documentation.md` | API endpoints, requests, responses, and errors |
| `05_Database_Schema.md` | Database and table structure, migrations, and how database sessions work |
| `06_JWT_Authentication_Flow.md` | Password security, tokens, and the authentication flow |
| `07_API_Testing_Report.md` | API test scenarios and results, with Swagger UI and Postman instructions |
| `08_Docker_Execution_Report.md` | Docker configuration, startup strategy, and test results |
| `09_Final_Completion_Report.md` | Final audit results, completion status, and pending work |
| `10_Teams_Progress_Updates.md` | Daily Teams updates |
| `postman/` | Postman collection and environment for the 22 API scenarios |
| `screenshots/` | Evidence screenshots, and a list explaining how each was captured |
