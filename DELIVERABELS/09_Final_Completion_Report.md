# Final Completion Report: ShopEase Auth Service

**Date:** 5 November 2026
**Name:** Anushree Yadav
**Status:** Implementation, testing, and the evidence screenshots are complete. The commit and the GitHub push are pending.

## Status summary

| Status | Items |
| --- | --- |
| **Completed** | All 5 authentication APIs, MySQL database and migrations, JWT security, Docker stack, automated tests, 22 API scenarios (on the API, through Swagger UI in a browser, and from a Postman collection in Newman), screenshots, README, and reports |
| **Failed** | Nothing in the final runs. See [Issues found during the audit](#issues-found-during-the-audit) for the checks that failed on earlier runs, and why. |
| **Pending** | Setting the Git email, the commit, and the manual push to GitHub |
| **Not done by a person** | Swagger UI was operated by a script, and the Postman desktop application was not used. See [Swagger UI and Postman](#swagger-ui-and-postman-testing-status). |
| **Known gaps** | No rate limiting, tokens that survive a password change, and dependency advisories with no fix. See [Pending work and blockers](#pending-work-and-blockers). |

There are no blockers. Nothing has been committed or pushed.

## Completed modules

| Module | Location | Status |
| --- | --- | --- |
| Configuration and secret validation | `app/core/config.py` | Completed |
| Password hashing and JWT handling | `app/core/security.py` | Completed |
| Database connection and sessions | `app/database/connection.py` | Completed |
| User model | `app/models/user_model.py` | Completed |
| Request and response schemas | `app/schemas/auth_schema.py` | Completed |
| Authentication business logic | `app/services/auth_service.py` | Completed |
| Authentication routes | `app/routers/auth_routes.py` | Completed |
| Error handling | `app/exception_handlers.py` | Completed |
| Migrations | `alembic/` | Completed |
| Containers | `Dockerfile`, `docker-compose.yml` | Completed |
| Automated tests | `tests/` | Completed |

No other microservice has been integrated.

## Implemented APIs

| Method | Path | Bearer token | Verified on Docker and MySQL |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | No | Yes |
| POST | `/api/auth/login` | No | Yes |
| GET | `/api/auth/me` | Yes | Yes |
| POST | `/api/auth/verify-token` | Yes | Yes |
| POST | `/api/auth/change-password` | Yes | Yes |
| GET | `/` | No | Published in the schema; not called directly in the final audit |
| GET | `/health` | No | Yes |
| GET | `/health/db` | No | Yes |

See the [API documentation](04_API_Documentation.md) for full details.

## Code audit

Tested on 5 November 2026 on a stack built with no cache and started from an empty volume.

| Requirement | Evidence | Result |
| --- | --- | --- |
| Required folders and files exist | 23 key files checked, and all 10 reports present | Passed |
| Registration works | 201 on MySQL, with role `USER` | Passed |
| Login works | 200 with a bearer token | Passed |
| Password hashing works | A 60-character bcrypt hash stored in MySQL | Passed |
| JWT generation works | Claims `sub`, `role`, `iat`, and `exp`, signed with HS256 | Passed |
| JWT verification works | Valid token accepted, and 27 of 27 bad requests returned 401 | Passed |
| Current-user API works | 200 with the correct user | Passed |
| Verify-token API works | 200 with `"valid": true` | Passed |
| Change-password API works | Only a message returned. The old password was rejected and the new one accepted. | Passed |
| Database connectivity works | `/health/db` reports connected, on `shopease_auth_db` and MySQL 8.4.11 | Passed |
| Alembic migrations work | Applied on startup, and `downgrade -1`, `downgrade base`, `upgrade head`, and `check` all succeeded | Passed |
| Docker Compose starts successfully | Exactly two services, both running and healthy | Passed |
| All required APIs are available through Swagger UI | All 8 routes published, and the 5 authentication APIs called through the page in Microsoft Edge | Passed; see [Swagger UI and Postman](#swagger-ui-and-postman-testing-status) |
| Automated tests pass | 299 passed, 0 failed, 1 warning | Passed |

The audit also ran the local commands from the README. Uvicorn on this machine connected to MySQL in the container, and registration and login worked.

## Security audit

| Requirement | Evidence | Result |
| --- | --- | --- |
| No plaintext passwords are stored | The table has `password_hash` and no password column. The submitted password was in no column of the user's row. | Passed |
| Password hashes are never returned | No bcrypt hash or `password_hash` in any response from the audit's API calls | Passed |
| JWT secrets are not hardcoded | No `.env` secret value in the text files among the 67 files Git would upload, and Compose only refers to variables | Passed |
| `.env` is ignored by Git | `git check-ignore` matched it, and a `git add` dry run left it out | Passed |
| `.env` is not copied into the Docker image | No `.env` file anywhere in the image's file system. No secret values in `/app`, image history, or image configuration. | Passed |
| Tokens expire correctly | A one-minute token returned 200, then 401 after a real 65-second wait. Normal lifetime is 1800 seconds, which matches the setting. | Passed |
| Inactive users cannot authenticate | Login returned 403, and an existing token returned 403 on all 3 protected endpoints | Passed |
| Protected endpoints reject invalid tokens | Missing, wrong scheme, empty, malformed, wrong secret, altered, `alg: none`, expired, and missing claims, on all 3 endpoints: 27 of 27 returned 401 | Passed |
| No secrets or real tokens in logs | Service, MySQL, and local Uvicorn logs scanned for secret values, test passwords, tokens, and hashes: none found | Passed |
| No secrets or real tokens in documentation | Every text file Git would upload scanned for secret values, whole JWTs, and whole bcrypt hashes: none found. The 11 images were checked by eye: no token, hash, or secret visible. | Passed |

Other results:

- A deleted user's token returned 401.
- Validation errors did not echo submitted passwords.
- The application and Compose refused to start from a fresh copy with no `.env`, and the application also refused the `.env.example` placeholders.
- The container runs as a non-root user.

## Database and migration status

| Item | Status |
| --- | --- |
| Database | `shopease_auth_db` on MySQL 8.4.11, in the `auth-mysql` container |
| Tables | `users` and `alembic_version` |
| Latest migration | `12ee6f689116`, change default role to `USER` |
| Migrations | `83f96cff2441` creates `users`, and `12ee6f689116` changes the default role |
| On startup | Each migration was applied once, and a restart did not repeat them |
| Models against the database | `alembic check` found no differences, from both the container and this machine |
| MySQL outage | With MySQL stopped, `/health` returned 200, and `/health/db` and login returned 503. The service reconnected when MySQL returned. |
| Data persistence | A user and their password survived `docker compose down` and `up` |

## JWT security implementation

- **Signing:** HMAC only (`HS256`, `HS384`, or `HS512`), with a secret of at least 32 characters read from the environment.
- **Validation:** only the configured algorithm is accepted, and `sub`, `role`, `iat`, and `exp` are all required.
- **Lifetime:** 30 minutes by default, set by `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Contents:** no email address, password, or hash.
- **One implementation:** `jwt.encode` and `jwt.decode` appear only in `app/core/security.py`, and all protected endpoints share the `get_current_user` dependency.
- **Database check:** each protected request loads the user, so deactivated and deleted users are rejected at once.
- **Errors:** all token failures return the same 401 message.

See the [JWT authentication flow](06_JWT_Authentication_Flow.md) for details.

## Docker execution status

**The containers started and the application connected to MySQL.** The image was built with no cache in 32 seconds, and the stack became healthy in 28 seconds from an empty volume. The other Docker checks are in the [Docker execution report](08_Docker_Execution_Report.md).

The test stack has been removed, so **no Auth Service containers are running now**. To start it again, run `docker compose up -d --build --wait`. Other projects' containers on this machine were not changed.

## Automated testing results

| Test run | Result |
| --- | --- |
| `python -m pytest` in the project | 299 passed, 0 failed, 1 `httpx` deprecation warning |
| `python -m pytest` on a fresh copy of the files Git would upload, with no `.env` | 299 passed, 0 failed, 1 warning |
| 22 mandatory scenarios on Docker and MySQL 8.4.11 | 22 of 22 passed, on each stack run in the final audit |
| 22 mandatory scenarios through Swagger UI in Microsoft Edge, operated by a script | 22 of 22 passed |
| 22 mandatory scenarios from the Postman collection in Newman 6.2.3 | 22 of 22 passed: 24 requests, 71 checks, 0 failed |
| Final audit checks with no Docker | 20 of 20 passed |
| Final audit checks on Docker and MySQL | 68 of 68 passed |
| `pip check` | No broken requirements |
| `pip-audit -r requirements.txt` | 3 known vulnerabilities across `python-jose` and `ecdsa`, with no fixed versions |

The scenarios and test suite were also checked by deliberately breaking the application, as described in the [API testing report](07_API_Testing_Report.md).

## Swagger UI and Postman testing status

| Item | Status |
| --- | --- |
| `/docs` and the OpenAPI schema over HTTP | Completed. All 8 routes and the Bearer scheme are published, and only the protected routes require it. |
| 22 scenarios through the real Swagger UI page | Completed: 22 of 22 passed. A script used **Try it out**, **Execute**, and **Authorize** in Microsoft Edge. |
| 22 scenarios from the Postman collection | Completed: 22 of 22 passed in Newman 6.2.3, Postman's command-line runner |
| **Logout** button in Swagger UI | Not used. Scenarios with no token ran on a newly loaded page. |
| Postman desktop application | **Not used.** It is not installed on this machine, so importing the collection into it has not been tried. |
| Operated by a person | **No.** Neither tool was operated by hand. |

See the [API testing report](07_API_Testing_Report.md) for the result of each scenario.

## Pending work and blockers

### Pending manual tasks

| Task | Owner | Note |
| --- | --- | --- |
| Set the Git email | Anushree Yadav | The configured `user.email` is still the placeholder `YOUR_GITHUB_EMAIL`. Fix it before the first commit. |
| Commit and push to GitHub | Anushree Yadav | The branch has no commits, and `.env` is not among the files Git would upload. |
| Optional: repeat by hand | Anushree Yadav | Only if a reviewer requires hand-taken screenshots or the Postman application. See the [screenshots folder](screenshots/README.md). |

### Known gaps

| Gap | Risk | Status |
| --- | --- | --- |
| No rate limiting on login and change-password | Passwords can be guessed repeatedly | Open. Needed before production use. |
| Tokens survive a password change | A stolen token keeps working until it expires, 30 minutes by default | Open. Needs a design decision and a database change. |
| `python-jose` 3.5.0 advisory, CVE-2026-85394 | Token forgery through algorithm confusion | Open, with no fixed release. Exposure is limited to HMAC decoding with a fixed algorithm. |
| `ecdsa` 0.19.2 advisory, CVE-2024-23342 | Timing attack on P-256 signing | Accepted. This service does not use ECDSA. |
| `python-jose` or `PyJWT` | Replacing the library would remove both advisories | Decision deferred |
| No HTTPS in the service | Credentials would be readable if exposed over plain HTTP | Ports are published on this machine only. Needs HTTPS before deployment. |
| `httpx` deprecation warning in tests | A future upgrade will need `httpx2` | Open. Tests still run. |

The README lists the other limitations, such as refresh tokens, password reset, and email verification, none of which were in scope.

### Not tested

- Several `auth-service` containers started at once. The migration strategy assumes one.
- A failed migration under Compose's restart policy. The failure was tested with a single `docker run`.
- Status code 500 on the running server. It was tested with a simulated failure in an automated test.
- Load or performance, other than the login timing comparison in the JWT report.
- Running on an operating system other than Windows 11.

## Issues found during the audit

No application fault was found, and the application code was not changed during the audit. All of these issues were in the audit itself:

| Issue | Resolution |
| --- | --- |
| The first live audit reported 21 of 23 checks passed. The scenario count read "0 PASS" because it did not allow for Windows line endings. | The script was fixed. The runner itself had reported 22 of 22 on that run. |
| The same run stopped early because the test client refused to send a header ending in a space | The check was changed, and the whole audit was rerun from an empty volume with 68 of 68 passed |
| `docker compose down` would have deleted logs before they were scanned | The script now saves the logs first, and scans them at the end |
| A check of the screenshot SQL failed because PowerShell 5.1 removed quotes from the test command | Rerun through Bash, where the SQL succeeded |
| The first Swagger UI script stopped because it read the table's "Code" header instead of the status code | The selector was fixed before any scenario was counted |
| The Postman collection first scored 21 of 22. Its TC-04 check compared two lists formatted differently, although the API returned the correct 422 and fields. | The check was fixed, and the whole stage was rerun |
| An empty `expired_token` would have let TC-14 pass in Postman, because an empty token also returns 401 | TC-14 now fails if the variable is empty, and the whole stage was rerun with 22 of 22 passed |

## Final deliverables

| File | Status |
| --- | --- |
| `README.md` | Completed |
| `DELIVERABELS/01_Project_Overview.md` | Completed |
| `DELIVERABELS/02_Day_1_Progress.md` | Completed |
| `DELIVERABELS/03_Day_2_Progress.md` | Completed |
| `DELIVERABELS/04_API_Documentation.md` | Completed |
| `DELIVERABELS/05_Database_Schema.md` | Completed |
| `DELIVERABELS/06_JWT_Authentication_Flow.md` | Completed |
| `DELIVERABELS/07_API_Testing_Report.md` | Completed |
| `DELIVERABELS/08_Docker_Execution_Report.md` | Completed |
| `DELIVERABELS/09_Final_Completion_Report.md` | Completed |
| `DELIVERABELS/10_Teams_Progress_Updates.md` | Completed |
| `DELIVERABELS/postman/` | Completed: the collection and the environment |
| `DELIVERABELS/screenshots/` | Completed: 11 images, and a README explaining how each was captured |
