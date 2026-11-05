# API Documentation: ShopEase Auth Service

Base URL for local development: `http://127.0.0.1:8001`

Interactive documentation is available at `/docs` when `DOCS_ENABLED=true`.

| Method | Path | Purpose | Authentication |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | Create a user account | None |
| POST | `/api/auth/login` | Log in and get an access token | None |
| GET | `/api/auth/me` | Get the current user's profile | Bearer token |
| POST | `/api/auth/verify-token` | Check an access token and get its user | Bearer token |
| POST | `/api/auth/change-password` | Change the current user's password | Bearer token |
| GET | `/` | Service information | None |
| GET | `/health` | Check that the API process is running | None |
| GET | `/health/db` | Check the database connection | None |
| GET | `/docs` | Swagger UI | None |

To call a protected endpoint from Swagger UI, log in, select **Authorize**, and paste the access token. Protected endpoints use HTTP Bearer authentication.

## Register a user

`POST /api/auth/register`

### Request

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `full_name` | string | Yes | 1 to 255 characters after trimming spaces |
| `email` | string | Yes | Valid email format. Trimmed and lowercased before saving. |
| `password` | string | Yes | See the password rules below |
| `confirm_password` | string | Yes | Must match `password` |

A password must:

- Have at least 8 characters
- Contain an uppercase letter, a lowercase letter, a number, and a special character
- Be at most 72 bytes long
- Not contain a null character

Other fields, such as `role` and `is_active`, are ignored. New accounts always have the role `USER` and are active.

```json
{
  "full_name": "Asha Rao",
  "email": "asha@example.com",
  "password": "Str0ng!Password",
  "confirm_password": "Str0ng!Password"
}
```

### Success: 201 Created

```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "full_name": "Asha Rao",
    "email": "asha@example.com",
    "role": "USER",
    "is_active": true
  }
}
```

### Errors

| Status | Cause | `detail` |
| --- | --- | --- |
| 409 | The email is already registered, in any letter case | `Email already registered` |
| 422 | A field is missing or invalid | `Validation failed`, with an `errors` list |
| 503 | The database is unavailable | `Service temporarily unavailable` |

## Log in

`POST /api/auth/login`

### Request

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `email` | string | Yes | Valid email format, in any letter case |
| `password` | string | Yes | Must not be empty |

```json
{
  "email": "asha@example.com",
  "password": "Str0ng!Password"
}
```

### Success: 200 OK

```json
{
  "message": "Login successful",
  "access_token": "<signed JWT>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "full_name": "Asha Rao",
    "email": "asha@example.com",
    "role": "USER",
    "is_active": true
  }
}
```

Send the token with requests to protected endpoints:

```text
Authorization: Bearer <access_token>
```

The token expires after `ACCESS_TOKEN_EXPIRE_MINUTES`.

### Errors

| Status | Cause | `detail` |
| --- | --- | --- |
| 401 | The email is unknown, or the password is wrong | `Invalid email or password` |
| 403 | The password is correct, but the account is inactive | `Inactive user` |
| 422 | A field is missing or invalid | `Validation failed`, with an `errors` list |
| 503 | The database is unavailable | `Service temporarily unavailable` |

An unknown email and a wrong password get the same response, so the API does not reveal which accounts exist through login. An inactive account is reported only when the password is correct.

## Get the current user

`GET /api/auth/me`

Returns the profile of the user who owns the token. The profile is read from the database on every request, so it reflects the user's current role and status.

### Request

The request has no body. It requires this header:

```text
Authorization: Bearer <access_token>
```

### Success: 200 OK

```json
{
  "id": 1,
  "full_name": "Asha Rao",
  "email": "asha@example.com",
  "role": "USER",
  "is_active": true
}
```

### Errors

| Status | Cause | `detail` |
| --- | --- | --- |
| 401 | The token is missing, malformed, wrongly signed, or expired | `Could not validate credentials` |
| 401 | The user no longer exists | `Could not validate credentials` |
| 403 | The user is inactive | `Inactive user` |
| 503 | The database is unavailable | `Service temporarily unavailable` |

## Verify a token

`POST /api/auth/verify-token`

Checks the access token in the `Authorization` header and confirms that its user still exists and is active. This endpoint does not issue or refresh tokens.

### Request

The request has no body. The token goes in the header, not the URL or body:

```text
Authorization: Bearer <access_token>
```

### Success: 200 OK

```json
{
  "valid": true,
  "user": {
    "id": 1,
    "full_name": "Asha Rao",
    "email": "asha@example.com",
    "role": "USER",
    "is_active": true
  }
}
```

`role` is the user's current role in the database, which may differ from the role in the token. The response does not include the token, its claims, its expiry time, or the signing algorithm.

### Errors

An invalid token returns an error status, not a 200 response with `"valid": false`. A client should treat any response other than 200 as not verified.

| Status | Cause | `detail` |
| --- | --- | --- |
| 401 | The token is missing, malformed, wrongly signed, or expired | `Could not validate credentials` |
| 401 | The user no longer exists | `Could not validate credentials` |
| 403 | The user is inactive | `Inactive user` |
| 503 | The database is unavailable | `Service temporarily unavailable` |

All token failures return the same 401 response, so a caller cannot learn why a token was rejected. Each 401 response includes the header `WWW-Authenticate: Bearer`.

## Change the password

`POST /api/auth/change-password`

Changes the password of the user who owns the token. The user is identified by the token, so this endpoint cannot change another user's password.

### Request

It requires this header:

```text
Authorization: Bearer <access_token>
```

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `current_password` | string | Yes | Must not be empty, and must match the stored password |
| `new_password` | string | Yes | Must follow the password rules for registration, and must differ from the current password |
| `confirm_new_password` | string | Yes | Must match `new_password` |

```json
{
  "current_password": "Str0ng!Password",
  "new_password": "N3w!StrongValue",
  "confirm_new_password": "N3w!StrongValue"
}
```

### Success: 200 OK

```json
{
  "message": "Password changed successfully"
}
```

The old password stops working for login at once, and the user's `updated_at` time is updated. Tokens that were already issued keep working until they expire. See the current limitations below.

### Errors

| Status | Cause | `detail` |
| --- | --- | --- |
| 400 | The current password is wrong | `Current password is incorrect` |
| 400 | The new password is the same as the current password | `New password must be different from the current password` |
| 401 | The token is missing, malformed, wrongly signed, or expired, or the user no longer exists | `Could not validate credentials` |
| 403 | The user is inactive | `Inactive user` |
| 422 | A field is missing, the new password is weak, or the confirmation does not match | `Validation failed`, with an `errors` list |
| 503 | The database is unavailable | `Service temporarily unavailable` |

## Error format

Every error response has a `detail` message:

```json
{
  "detail": "Email already registered"
}
```

Validation errors also list each invalid field:

```json
{
  "detail": "Validation failed",
  "errors": [
    {
      "field": "password",
      "message": "Password must contain a number, contain a special character"
    }
  ]
}
```

| Status | Meaning |
| --- | --- |
| 200 | Successful login, protected request, or password change |
| 201 | Successful registration |
| 400 | The operation was refused, such as a failed password change |
| 401 | Credentials or token are invalid |
| 403 | The account is inactive |
| 404 | The path does not exist |
| 405 | The method is not allowed on this path |
| 409 | The request conflicts with existing data |
| 422 | The request data is invalid |
| 500 | Unexpected server error, with the message `Internal server error` |
| 503 | The database is unavailable |

No endpoint returns 204, because each successful response has a body.

Error responses never include passwords, password hashes, submitted values, or connection details.

## Service endpoints

| Path | Success response | Failure response |
| --- | --- | --- |
| `GET /` | 200: `{"service": "ShopEase Auth Service", "version": "0.1.0", "docs_url": "/docs"}` | None |
| `GET /health` | 200: `{"status": "ok", "service": "ShopEase Auth Service", "version": "0.1.0"}` | None |
| `GET /health/db` | 200: `{"status": "ok", "database": "connected"}` | 503: `{"detail": "Database unavailable"}` |

`docs_url` is `null` when `DOCS_ENABLED=false`.

## Current limitations

- **No rate limiting:** the login and change-password endpoints do not limit repeated attempts. Add this in the service or at the API gateway before production use.
- **Existing tokens survive a password change:** a token issued before the change keeps working until it expires, which is 30 minutes by default. If a token was stolen, changing the password does not cancel it.
- **Email ownership is not verified:** registration only checks the address format, not that the user owns it.
- **Registration reveals existing emails:** the 409 response shows that an address is already registered.
