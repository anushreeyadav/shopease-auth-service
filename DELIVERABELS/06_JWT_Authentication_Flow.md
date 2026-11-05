# JWT Authentication Flow: ShopEase Auth Service

## Current status

The password and token functions and the route dependencies are implemented and tested in `app/core/security.py`. Registration and login use them through `app/services/auth_service.py`, and `GET /api/auth/me`, `POST /api/auth/verify-token`, and `POST /api/auth/change-password` are protected by the route dependencies. See the [API documentation](04_API_Documentation.md) for request and response details.

## Overview

The service proves a user's identity with a signed JSON Web Token (JWT):

1. A user logs in with an email address and password.
2. The service checks the password and issues a signed access token.
3. The client sends the token with each protected request.
4. The service checks the token and then loads the user from the database.

```text
Client                        Auth Service                       MySQL
  |                                |                               |
  |-- POST email and password ---->|                               |
  |                                |-- find user by email -------->|
  |                                |<-- user and password hash ----|
  |                                |   verify_password()           |
  |                                |   create_access_token()       |
  |<-- access token ---------------|                               |
  |                                |                               |
  |-- Authorization: Bearer ------>|                               |
  |                                |   decode_access_token()       |
  |                                |-- load user by ID ----------->|
  |                                |<-- current user record -------|
  |                                |   check is_active             |
  |<-- protected response ---------|                               |
```

## Password security

| Function | Purpose |
| --- | --- |
| `validate_password_strength()` | Rejects weak passwords and lists every unmet rule |
| `hash_password()` | Creates a salted bcrypt hash with Passlib |
| `verify_password()` | Compares a password with a stored hash |

A password must:

- Have at least 8 characters
- Contain an uppercase letter, a lowercase letter, a number, and a special character
- Be at most 72 bytes long, because bcrypt ignores anything after 72 bytes
- Not contain a null character, which bcrypt cannot hash

Passwords are protected at three points:

- **Storage:** the database has a `password_hash` column and no password column. The `User` model rejects any value that is not in bcrypt format.
- **Responses:** `UserResponse` has no password field, so routes that use it as their response model cannot return the hash.
- **Errors:** error messages never include the password or the rejected value.

`RegisterRequest` and `ChangePasswordRequest` apply the strength rules, so a weak password is rejected before `hash_password()` runs.

## Login checks

`login_user()` in `app/services/auth_service.py` applies these checks in order:

1. **Find the user:** the email is normalized and looked up. If it is unknown, a password check still runs against a dummy hash, so that response times do not reveal which emails exist. The request then fails with 401.
2. **Verify the password:** a wrong password fails with the same 401 response.
3. **Check the account:** an inactive account fails with 403. This comes last, so only someone with the correct password learns the account's status.
4. **Issue the token:** an access token is created with the user's ID and role.

## Access tokens

`create_access_token()` signs these claims:

| Claim | Meaning | Example |
| --- | --- | --- |
| `sub` | User ID, as a string | `"42"` |
| `role` | User's role when the token was issued | `"USER"` |
| `iat` | Time the token was issued | `1793779200` |
| `exp` | Time the token expires | `1793781000` |

| Setting | Purpose |
| --- | --- |
| `JWT_SECRET_KEY` | Signing secret, read from the environment and never hardcoded |
| `JWT_ALGORITHM` | Signing algorithm: `HS256`, `HS384`, or `HS512` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |

Token contents are signed but not encrypted, so anyone holding a token can read its claims. Tokens therefore contain no email address, password, or hash.

## Token validation

`decode_access_token()` raises `InvalidTokenError` for any token that fails these checks:

| Token problem | How it is rejected |
| --- | --- |
| Expired | `exp` is checked against the current time |
| Malformed | The token cannot be parsed as a JWT |
| Invalid signature or changed contents | The signature does not match the secret |
| Unsigned (`alg: none`) or a different algorithm | Only the configured algorithm is accepted |
| Missing `sub`, `role`, `iat`, or `exp` | Required claims are checked |
| `sub` is not a whole number, or `role` is not a non-empty string | Claim values are checked |

## Route dependencies

Each dependency builds on the one before it:

| Dependency | Returns | Queries the database | Use it when |
| --- | --- | --- | --- |
| `get_token_payload` | User ID and role from the token | No | Only the token's claims are needed |
| `get_current_user_id` | User ID from the token | No | Only the ID is needed, and a deactivated user may still pass |
| `get_current_user` | Current `User` record | Yes | **Default for protected routes** |

```python
@router.get("/me", response_model=UserResponse)
def read_current_user(user: User = Depends(get_current_user)):
    return user
```

### Protected endpoints

`GET /api/auth/me`, `POST /api/auth/verify-token`, and `POST /api/auth/change-password` all use `get_current_user`. All JWT encoding and decoding stays in `app/core/security.py`, so the endpoints cannot apply different rules.

A request to any of these endpoints follows these steps:

1. **Read the token:** `HTTPBearer` reads the `Authorization` header. A missing header or a different scheme fails with 401.
2. **Validate the token:** `decode_access_token()` checks the signature, algorithm, expiry, and required claims. Any failure returns 401.
3. **Extract the claims:** the user ID comes from `sub`, and the role comes from `role`.
4. **Load the user:** `get_current_user` reads the user from MySQL by ID. If the user no longer exists, the request fails with 401.
5. **Check the status:** an inactive user fails with 403.
6. **Respond:** `me` and `verify-token` return only the fields in `UserResponse`, and `verify-token` also returns `"valid": true`. `change-password` first applies the checks below, then returns only a message.

The `me` and `verify-token` responses use the role from the database, not from the token. The token's `role` claim is validated but does not affect either response.

### Changing a password

`change_password()` in `app/services/auth_service.py` runs after the steps above:

1. **Verify the current password:** a wrong password fails with 400.
2. **Compare the passwords:** a new password that is the same as the current one fails with 400.
3. **Save the new hash:** `hash_password()` creates the hash and the change is committed, which also updates `updated_at`.

`ChangePasswordRequest` has already rejected a weak new password or a mismatched confirmation with 422.

### Why the database is checked

A token stays valid until it expires, even if the account changes after it was issued. `get_current_user` therefore loads the user on every request:

| Account change | Effect on a token that has not expired |
| --- | --- |
| User deactivated (`is_active` is false) | Rejected with 403 on the next request |
| User reactivated | Accepted again |
| User deleted | Rejected with 401 on the next request |
| Role changed | `user.role` has the new role at once, but the token's `role` claim does not change |

Permission checks must use `user.role` from `get_current_user`, not the token's `role` claim.

## Error responses

These responses apply to routes protected by the dependencies above. The API documentation lists the login errors.

| Situation | Status | Response body |
| --- | --- | --- |
| Token is missing, expired, malformed, or invalid | 401 | `{"detail": "Could not validate credentials"}` |
| User no longer exists | 401 | `{"detail": "Could not validate credentials"}` |
| User is inactive | 403 | `{"detail": "Inactive user"}` |

All token failures return the same message, so a caller cannot learn why a token was rejected. Each 401 response also includes `WWW-Authenticate: Bearer`.

## Testing

Run the unit tests from the project root. They use an in-memory SQLite database and test-only secrets, so they need neither MySQL nor `.env`.

```powershell
python -m pytest
```

| File | Covers |
| --- | --- |
| `tests/test_password_security.py` | Hashing, verification, strength rules, and the plaintext guard |
| `tests/test_jwt.py` | Token generation, decoding, expiration, and rejected tokens |
| `tests/test_auth_dependencies.py` | Protected routes, including deleted and deactivated users |
| `tests/test_auth_api.py` | Registration and login through the real application |
| `tests/test_protected_api.py` | `me` and `verify-token` with valid, missing, invalid, and expired tokens, and inactive and deleted users |
| `tests/test_change_password_api.py` | Password changes, including rejected requests and login afterwards |
| `tests/test_app_integration.py` | Registered routes, Swagger UI, Bearer authentication, status codes, sensitive data, and session closing |
| `tests/test_api_scenarios.py` | The 22 mandatory API scenarios from the [API testing report](07_API_Testing_Report.md) |

### Results

Tested on 4 November 2026.

| Check | Result |
| --- | --- |
| Automated tests | 276 passed on 4 November, with 1 deprecation warning about `httpx` and the test client. See the [API testing report](07_API_Testing_Report.md) for the later total. |
| Deliberately broken security and API code, 60 variations | All caught by the tests, after one test was corrected |
| One-off script for hashing, tokens, and dependencies against a running MySQL 8.4.11 container, 9 checks | All passed |
| One-off script for registration and login over HTTP against MySQL, 16 checks | All passed |
| One-off script for `me` and `verify-token` over HTTP against MySQL, 16 checks | All passed |
| One-off script for the complete application, including password changes, against MySQL, 37 checks | All passed |
| Median login time, wrong password and unknown email | 348 ms and 308 ms |

The first MySQL script stored a bcrypt hash and verified it. Using one token, it then confirmed that direct database changes to a user's status and role took effect, and that the token stopped working once the user was deleted.

The final audit on 5 November 2026 repeated the token checks through the Docker containers and MySQL:

| Check | Result |
| --- | --- |
| Missing, wrong scheme, empty, malformed, wrong secret, altered, `alg: none`, expired, and missing claims, on all 3 protected endpoints | 27 of 27 returned 401 |
| Token with a one-minute lifetime | 200 at first, and 401 after a real 65-second wait |
| Normal token lifetime | 1800 seconds, matching `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Inactive user | Login and all 3 protected endpoints returned 403 |
| Deleted user | Existing token returned 401 |

See the [final completion report](09_Final_Completion_Report.md).

## Known limitations

- **No rate limiting:** repeated login and password change attempts are not limited.
- **No token revocation:** a token cannot be cancelled individually, and changing the password does not cancel existing tokens. Deactivating the user is the way to block access before the token expires.
- **Advisories in `python-jose`:** version 3.5.0 has an advisory with no fixed release (CVE-2026-85394). Restricting decoding to the configured HMAC algorithm limits the exposure. See the project overview for details.
- **Shared secret:** any service that holds `JWT_SECRET_KEY` can also create valid tokens, so it must be shared as little as possible.
