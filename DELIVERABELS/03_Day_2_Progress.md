# Day 2 Progress Report

**Date:** 4 November 2026 (Day 2 work completed ahead of schedule, on the same date as Day 1)
**Name:** Anushree Yadav
**Status:** Completed

## Planned tasks

- [x] Implement `GET /api/auth/me`
- [x] Implement `POST /api/auth/verify-token`
- [x] Reuse the existing security dependencies, with no duplicated JWT validation
- [x] Add automated tests for valid, missing, invalid, expired, and inactive-user tokens
- [x] Update the API and JWT authentication documentation
- [x] Implement `POST /api/auth/change-password`
- [x] Review the complete application: routes, API information, Swagger UI, Bearer authentication, error handling, sessions, and status codes
- [x] Run the complete automated test suite and fix any failures

## Completed work

- **Current user API:** implemented `GET /api/auth/me`, which requires a Bearer token and returns the user's profile from MySQL.
- **Token verification API:** implemented `POST /api/auth/verify-token`, which requires a Bearer token and returns `"valid": true` with the user's profile.
- **Shared validation:** both endpoints use the `get_current_user` dependency. All JWT encoding and decoding stays in `app/core/security.py`.
- **Account checks:** both endpoints reject missing, malformed, wrongly signed, and expired tokens, as well as deleted and inactive users.
- **Safe responses:** both endpoints return only the user's ID, full name, email, role, and account status. They never return the password hash, JWT secret, token claims, or signing algorithm.
- **Documentation:** added both endpoints to the API documentation and described the protected request flow in the JWT authentication document.
- **Change password API:** implemented `POST /api/auth/change-password`. It requires a Bearer token, checks the current password, and stores the new password as a bcrypt hash. The old password stops working at once, and `updated_at` is updated.
- **Password change rules:** a wrong current password or reuse of the current password returns 400. A weak new password or a mismatched confirmation returns 422. The response contains only a success message.
- **Application review:** all five authentication endpoints are registered, and Swagger UI is available at `/docs` with HTTP Bearer authentication. `GET /health`, centralized error handling, and database session closing were already in place, and are now covered by tests. The API description was extended.
- **API documentation:** `04_API_Documentation.md` now has the complete endpoint list, response examples, and status codes.

The code is local and has not been pushed to GitHub yet.

## Files created or changed

| File | Change |
| --- | --- |
| `app/routers/auth_routes.py` | Added the three protected endpoints |
| `app/services/auth_service.py` | Added `change_password` and its two errors |
| `app/schemas/auth_schema.py` | Added `TokenVerificationResponse`, `ChangePasswordRequest`, and `MessageResponse`; removed an internal note from the public API schema |
| `app/main.py` | Extended the API description |
| `app/core/security.py` | Corrected a comment |
| `tests/test_protected_api.py` | Added tests for `me` and `verify-token` |
| `tests/test_change_password_api.py` | Added tests for changing the password |
| `tests/test_app_integration.py` | Added tests for routes, documentation, status codes, sensitive data, and session closing |
| `DELIVERABELS/04_API_Documentation.md` | Added the new endpoints, response examples, and status codes |
| `DELIVERABELS/06_JWT_Authentication_Flow.md` | Added the protected request flow, password change flow, and test results |
| `DELIVERABELS/01_Project_Overview.md`, `README.md` | Updated the current status and endpoint list |

## Testing and results

| Check | Command or method | Result |
| --- | --- | --- |
| Complete automated test suite | `python -m pytest` | 276 passed, 0 failed, with 1 deprecation warning. 121 of these tests were added in the Day 2 work. |
| Test effectiveness | Deliberately broke the code in 32 ways | All caught, after one test was corrected (see Issues) |
| `me` and `verify-token` over HTTP against MySQL 8.4.11 | One-off script, 16 checks | All passed |
| Complete application against MySQL 8.4.11 | One-off script, 37 checks | All passed |
| Password change against MySQL | Part of the 37 checks | The old password returned 401, the new password returned 200, the hash changed, and `updated_at` moved forward |
| Status codes against MySQL | Part of the 37 checks | 200, 201, 400, 401, 404, 409, 422, and 503 all returned as expected |
| Status code 500 | Automated test with a simulated failure | Returned the generic `Internal server error`. It was not triggered on the running server. |
| Database sessions | 100 requests against MySQL, including failed ones | No connections left in use |
| Database stopped during testing | One-off script | Login and change password returned 503, and `/health` still returned 200 |
| Expired token signed with the real secret | One-off script | Both endpoints returned 401 |
| Status and role changed directly in MySQL | One-off script, reusing one token | Inactive returned 403, reactivated returned 200, deleted returned 401, and a role change appeared at once |
| JWT logic in one place | Searched the application code | `jwt.encode` and `jwt.decode` appear only in `app/core/security.py` |
| Secrets in API container logs | Searched for passwords, hashes, tokens, and secrets | None found |

The MySQL tests used a temporary container, which was removed afterwards.

## Screenshots

None were captured on this day. Evidence screenshots were captured on 5 November 2026, and are in the [screenshots folder](screenshots/README.md).

## Issues and resolutions

| Issue | Resolution |
| --- | --- |
| `verify-token` could report an invalid token as either an error or `"valid": false` | Invalid tokens return 401, because the endpoint requires a valid token. Callers must treat any response other than 200 as not verified. |
| The token's role can become out of date after a role change | Both endpoints return the current role from the database. |
| A new test found an internal note about `password_hash` in the public API schema, published from a code docstring | Fixed. The note is now a code comment. No user data was exposed. |
| One deliberate code break was not caught: checking for password reuse before checking the current password | Fixed. Added a test for this order, and all 20 breaks for the final two prompts were then caught. |
| Tokens issued before a password change keep working until they expire, 30 minutes by default | Open. Confirmed against MySQL. Cancelling them needs a design decision and a database change. |
| The change-password endpoint does not limit repeated attempts | Open. Someone holding a stolen token could keep guessing the current password. Login has the same limitation. |
| A database failure returns 503, not the 500 listed in the requirements | Kept on purpose. 503 tells the client to retry later, and 500 is still returned for other unexpected errors. |
| `python-jose` 3.5.0 has an advisory with no fixed release (CVE-2026-85394) | Open. Token decoding accepts only the configured HMAC algorithm, which limits the exposure. |
| Starlette warns that using `httpx` with its test client is deprecated | Open. Tests still run, but `httpx2` will be needed in a future upgrade. |

## Plan for tomorrow

- Capture evidence screenshots for the completed work.
- Continue with the remaining Auth Service work.

## Later work

The work after this report, on 5 November 2026, is recorded in the [Docker execution report](08_Docker_Execution_Report.md), the [API testing report](07_API_Testing_Report.md), and the [final completion report](09_Final_Completion_Report.md).
