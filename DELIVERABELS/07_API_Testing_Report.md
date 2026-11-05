# API Testing Report: ShopEase Auth Service

**Date:** 5 November 2026
**Name:** Anushree Yadav
**Result:** 22 of 22 scenarios passed.

## Summary

| Test run | Environment | Result |
| --- | --- | --- |
| 22 mandatory scenarios over HTTP | `auth-service` and `auth-mysql` containers, MySQL 8.4.11 | 22 of 22 scenarios passed. This run produced the results below. |
| 22 mandatory scenarios through the application | In-memory SQLite, `tests/test_api_scenarios.py` | All passed |
| Complete automated test suite | In-memory SQLite, `python -m pytest` | 299 passed, 0 failed, with 1 `httpx` deprecation warning |
| Rerun during the final audit | Stacks built again on 5 November 2026 | 22 of 22 passed on each run. The final audit's result rows were identical to those below. |

| 22 mandatory scenarios through Swagger UI | The real `/docs` page in Microsoft Edge, operated by a script | 22 of 22 scenarios passed |
| 22 mandatory scenarios from the Postman collection | Newman 6.2.3, Postman's command-line runner | 22 of 22 scenarios passed |

**No person operated Swagger UI or Postman, and the Postman desktop application was not used.** See [Swagger UI and Postman collection results](#swagger-ui-and-postman-collection-results) for exactly how those runs took place.

All credentials in this report are dummy test values. Tokens were never recorded. `<run>` stands for a unique number from each test run, and the runner deletes its test users afterwards.

## Test results

Each result was recorded by `tests/run_live_scenarios.py` when the scenario ran. A scenario gets PASS only if both its status code and its response content are correct.
### Registration

| ID | Endpoint | Request | Expected status | Actual status | Expected result | Actual result | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-01 | `POST /api/auth/register` | New email `tc01.<run>@example.com`, password and confirm_password `Test!Pass123` | 201 | 201 | The user is created with role USER and is active. No password data is returned. | `User registered successfully`. Role `USER`, active `true`. | PASS |
| TC-02 | `POST /api/auth/register` | The same email, `tc02.<run>@example.com`, is registered a second time | 409 | 409 | The request is rejected with `Email already registered`. | `Email already registered` | PASS |
| TC-03 | `POST /api/auth/register` | Email `not-an-email`, with otherwise valid fields | 422 | 422 | The request is rejected with a validation error on `email`. | `Validation failed` on `email` | PASS |
| TC-04 | `POST /api/auth/register` | Only `email` is sent. `full_name`, `password`, and `confirm_password` are missing. | 422 | 422 | The request is rejected with a validation error on each missing field. | `Validation failed` on `full_name`, `password`, `confirm_password` | PASS |
| TC-05 | `POST /api/auth/register` | password `Test!Pass123`, confirm_password `Wrong!Pass789` | 422 | 422 | The request is rejected with `Passwords do not match` on `confirm_password`. | `Validation failed` on `confirm_password` | PASS |
| TC-06 | `POST /api/auth/register` | password and confirm_password `weak` | 422 | 422 | The request is rejected with the unmet strength rules on `password`. The password is not echoed. | `Validation failed` on `password` | PASS |

### Login

| ID | Endpoint | Request | Expected status | Actual status | Expected result | Actual result | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-07 | `POST /api/auth/login` | Registered email `tc07.<run>@example.com`, password `Test!Pass123` | 200 | 200 | An access token and the user's profile are returned. | `Login successful`. Token returned (value not recorded). Role `USER`. | PASS |
| TC-08 | `POST /api/auth/login` | Registered email `tc08.<run>@example.com`, password `Wrong!Pass789` | 401 | 401 | The login is rejected with `Invalid email or password`. No token is returned. | `Invalid email or password` | PASS |
| TC-09 | `POST /api/auth/login` | Unregistered email `tc09.<run>@example.com`, password `Test!Pass123` | 401 | 401 | The login gets the same rejection as a wrong password, so the email's existence is not revealed. | `Invalid email or password` | PASS |
| TC-10 | `POST /api/auth/login` | Email `tc10.<run>@example.com`, password `Test!Pass123`. `is_active` was set to false in the database first. | 403 | 403 | The login is rejected with `Inactive user`. No token is returned. | `Inactive user` | PASS |

### JWT authentication

| ID | Endpoint | Request | Expected status | Actual status | Expected result | Actual result | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-11 | `GET /api/auth/me` | `Authorization: Bearer <token from login>` | 200 | 200 | The user's profile is returned, with no password data. | Profile returned, with fields email, full_name, id, is_active, role | PASS |
| TC-12 | `GET /api/auth/me` | No `Authorization` header | 401 | 401 | The request is rejected with `Could not validate credentials`. | `Could not validate credentials` | PASS |
| TC-13 | `GET /api/auth/me` | `Authorization: Bearer not-a-valid-token` | 401 | 401 | The request is rejected with `Could not validate credentials`. | `Could not validate credentials` | PASS |
| TC-14 | `GET /api/auth/me` | `Authorization: Bearer <correctly signed token that expired 1 second ago>`, for an existing user | 401 | 401 | The request is rejected with `Could not validate credentials`. | `Could not validate credentials` | PASS |
| TC-15 | `POST /api/auth/verify-token` | `Authorization: Bearer <token from login>` | 200 | 200 | The response has `"valid": true` and the user's profile. | `valid: true`, with fields email, full_name, id, is_active, role | PASS |
| TC-16 | `POST /api/auth/verify-token` | `Authorization: Bearer not-a-valid-token` | 401 | 401 | The request is rejected with `Could not validate credentials`. | `Could not validate credentials` | PASS |

### Change password

| ID | Endpoint | Request | Expected status | Actual status | Expected result | Actual result | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-17 | `POST /api/auth/change-password` | Bearer token, current_password `Test!Pass123`, new_password and confirm_new_password `New!Pass456` | 200 | 200 | The password is changed, and only a success message is returned. | `Password changed successfully` | PASS |
| TC-18 | `POST /api/auth/change-password` | Bearer token, current_password `Wrong!Pass789`, new_password and confirm_new_password `New!Pass456` | 400 | 400 | The change is rejected with `Current password is incorrect`. | `Current password is incorrect` | PASS |
| TC-19 | `POST /api/auth/change-password` | Bearer token, current_password `Test!Pass123`, new_password and confirm_new_password `weak` | 422 | 422 | The change is rejected with the unmet strength rules on `new_password`. | `Validation failed` on `new_password` | PASS |
| TC-20 | `POST /api/auth/change-password` | No `Authorization` header, current_password `Test!Pass123`, new_password and confirm_new_password `New!Pass456` | 401 | 401 | The request is rejected with `Could not validate credentials`. | `Could not validate credentials` | PASS |
| TC-21 | `POST /api/auth/login` | After changing the password from `Test!Pass123` to `New!Pass456`, log in with `New!Pass456` | 200 | 200 | The login succeeds with the new password. | `Login successful`. Token returned (value not recorded). Role `USER`. | PASS |
| TC-22 | `POST /api/auth/login` | After changing the password from `Test!Pass123` to `New!Pass456`, log in with `Test!Pass123` | 401 | 401 | The login is rejected with `Invalid email or password`. | `Invalid email or password` | PASS |


## Swagger UI and Postman collection results

These runs took place on 5 November 2026, against the Docker containers and MySQL 8.4.11.

| Item | How it ran |
| --- | --- |
| Swagger UI | A script operated the real page at `/docs` in Microsoft Edge, using **Try it out**, **Execute**, and **Authorize**. It read each status code from the page. No person operated the browser. |
| Postman collection | [The collection](postman/ShopEase_Auth_Service.postman_collection.json) ran in Newman 6.2.3, Postman's command-line runner: 24 requests and 71 checks, with none failed. **The Postman desktop application is not installed on this machine, so it was not used.** |
| TC-10 setup | A script deactivated the user in the database |
| TC-14 setup | A script signed a token with the real secret that had expired 1 second earlier |
| TC-12 and TC-20 | Each ran on a newly loaded Swagger UI page with no token, so the **Logout** button was not used |

| ID | Endpoint | Expected status | Swagger UI status | Swagger UI result | Newman status | Newman result |
| --- | --- | --- | --- | --- | --- | --- |
| TC-01 | `/api/auth/register` | 201 | 201 | PASS | 201 | PASS |
| TC-02 | `/api/auth/register` | 409 | 409 | PASS | 409 | PASS |
| TC-03 | `/api/auth/register` | 422 | 422 | PASS | 422 | PASS |
| TC-04 | `/api/auth/register` | 422 | 422 | PASS | 422 | PASS |
| TC-05 | `/api/auth/register` | 422 | 422 | PASS | 422 | PASS |
| TC-06 | `/api/auth/register` | 422 | 422 | PASS | 422 | PASS |
| TC-07 | `/api/auth/login` | 200 | 200 | PASS | 200 | PASS |
| TC-08 | `/api/auth/login` | 401 | 401 | PASS | 401 | PASS |
| TC-09 | `/api/auth/login` | 401 | 401 | PASS | 401 | PASS |
| TC-10 | `/api/auth/login` | 403 | 403 | PASS | 403 | PASS |
| TC-11 | `/api/auth/me` | 200 | 200 | PASS | 200 | PASS |
| TC-12 | `/api/auth/me` | 401 | 401 | PASS | 401 | PASS |
| TC-13 | `/api/auth/me` | 401 | 401 | PASS | 401 | PASS |
| TC-14 | `/api/auth/me` | 401 | 401 | PASS | 401 | PASS |
| TC-15 | `/api/auth/verify-token` | 200 | 200 | PASS | 200 | PASS |
| TC-16 | `/api/auth/verify-token` | 401 | 401 | PASS | 401 | PASS |
| TC-17 | `/api/auth/change-password` | 200 | 200 | PASS | 200 | PASS |
| TC-18 | `/api/auth/change-password` | 400 | 400 | PASS | 400 | PASS |
| TC-19 | `/api/auth/change-password` | 422 | 422 | PASS | 422 | PASS |
| TC-20 | `/api/auth/change-password` | 401 | 401 | PASS | 401 | PASS |
| TC-21 | `/api/auth/login` | 200 | 200 | PASS | 200 | PASS |
| TC-22 | `/api/auth/login` | 401 | 401 | PASS | 401 | PASS |

## How the tests were checked

| Check | Result |
| --- | --- |
| Deliberately broke the application in 14 ways, then ran the scenarios | 13 caught by the scenarios. The other, removing the duplicate email check, still returned 409 because of the database's unique index. The registration tests in the full suite caught it. |
| Ran the runner against an address with no service | 0 of 22 passed, with exit code 1, so a scenario that cannot run is reported as a failure |
| Scanned this report for the real secrets in `.env` and for JWT values | None found |

The first round of deliberate breaks found a weakness in the scenarios: TC-12 ran on an empty test database, so a bypass of the token check was not detected. TC-12, TC-13, TC-16, and TC-20 now create a user first, and the bypass is caught by TC-12 and TC-20. The application had no fault.

## Repeat the automated tests

```powershell
# The 22 scenarios on SQLite. Needs neither Docker nor .env.
python -m pytest tests/test_api_scenarios.py

# The complete test suite.
python -m pytest

# The 22 scenarios against the running containers and MySQL. Prints the result tables.
docker compose up -d --build --wait
python -m tests.run_live_scenarios
```

## Prepare for manual testing

Start the service:

```powershell
docker compose up -d --build --wait
```

Manual tests keep their users in the database, so use a new email address if you repeat a registration. To start again with an empty database, run `docker compose down -v`, which **deletes all database data**, and then start the service again.

Use these dummy test values:

| Item | Value |
| --- | --- |
| Email | `manual.test@example.com` |
| Password | `Test!Pass123` |
| New password | `New!Pass456` |
| Wrong password | `Wrong!Pass789` |
| Weak password | `weak` |
| Invalid token | `not-a-valid-token` |

Run the change password scenarios in this order: TC-18, TC-19, TC-20, TC-17, TC-21, TC-22. TC-17 changes the password, so the earlier scenarios need the original one.

### Create an inactive account (TC-10)

The API cannot deactivate an account, so change it in the database. Register `inactive.test@example.com`, then open MySQL. The command asks for `MYSQL_ROOT_PASSWORD` from your `.env`:

```powershell
docker compose exec auth-mysql mysql -uroot -p shopease_auth_db
```

At the `mysql>` prompt, run:

```sql
UPDATE users SET is_active = 0 WHERE email = 'inactive.test@example.com';
exit
```

This SQL was tested through a script, not by typing it at the prompt. Login returned 403 after the update.

### Get an expired token (TC-14)

Restart the service with a one-minute token lifetime. This does not change `.env`:

```powershell
$env:ACCESS_TOKEN_EXPIRE_MINUTES = '1'
docker compose up -d --wait auth-service
```

Log in, copy the token, wait more than a minute, and then call `GET /api/auth/me` with that token. Then restore the normal lifetime:

```powershell
Remove-Item Env:ACCESS_TOKEN_EXPIRE_MINUTES
docker compose up -d --wait auth-service
```

This was tested with a real wait: the token returned 200 at first, and 401 after 65 seconds.

## Test with Swagger UI

1. Open `http://127.0.0.1:8001/docs`.
2. Select an endpoint, then **Try it out**.
3. Enter the request body from the results tables, then select **Execute**.
4. Compare the **Code** and the response body with the expected values.

To call a protected endpoint:

1. Run `POST /api/auth/login`, and copy the `access_token` value from the response.
2. Select **Authorize** at the top of the page.
3. Paste only the token into the **Value** box. Do not type `Bearer`, because Swagger UI adds it.
4. Select **Authorize**, then **Close**.

| Scenario | How to set the token |
| --- | --- |
| TC-11, TC-15, TC-17, TC-18, TC-19 | Authorize with the token from login |
| TC-12, TC-20 | Select **Authorize**, then **Logout**, so that no token is sent |
| TC-13, TC-16 | Authorize with `not-a-valid-token` |
| TC-14 | Authorize with the expired token |

## Test with Postman

### Import the ready-made collection

The collection contains all 22 scenarios with their checks, and uses dummy values only. It ran in Newman, but importing it into the Postman desktop application has not been tried.

1. In Postman, select **Import**, then select both files in [`DELIVERABELS/postman/`](postman/).
2. Select the `ShopEase Auth Local` environment in the top-right corner.
3. For TC-10, register `inactive.test@example.com` with the password `Test!Pass123`, then deactivate it as described in [Create an inactive account](#create-an-inactive-account-tc-10).
4. For TC-14, get an expired token as described in [Get an expired token](#get-an-expired-token-tc-14), and paste it into the `expired_token` environment variable. TC-14 fails if this variable is empty, because an empty token would also return 401.
5. Run the collection, keeping its order. The change password scenarios are in the order TC-18, TC-19, TC-20, TC-17, TC-21, TC-22.

To run it again, clear the collection's `run_id` variable, so that it creates new test emails. Do not share or export an environment that holds a token.

To run it from the command line, set the two values first:

```powershell
npx newman run DELIVERABELS/postman/ShopEase_Auth_Service.postman_collection.json `
  -e DELIVERABELS/postman/ShopEase_Auth_Local.postman_environment.json `
  --env-var "expired_token=<expired token>"
```

### Set up the environment yourself

Use these steps instead of the import if you want to build the requests yourself.


1. Select **Environments**, then create one named `ShopEase Auth`.
2. Add the variable `base_url` with the value `http://127.0.0.1:8001`.
3. Add the variable `access_token`, and leave it empty.
4. Select the environment in the top-right corner.

### Get a token

1. Create a `POST` request to `{{base_url}}/api/auth/login`.
2. In **Body**, select **raw** and **JSON**, then enter:

   ```json
   {
     "email": "manual.test@example.com",
     "password": "Test!Pass123"
   }
   ```

3. In **Scripts**, select **Post-response**, then enter this script. It saves the token to the environment after each successful login:

   ```javascript
   if (pm.response.code === 200) {
     pm.environment.set("access_token", pm.response.json().access_token);
   }
   ```

4. Select **Send**. Register the user first if the response is 401.

Do not share or export an environment that holds a live token.

### Configure Bearer Token authentication

1. Create a request, such as `GET {{base_url}}/api/auth/me`.
2. Open the **Authorization** tab.
3. Set **Auth Type** to **Bearer Token**.
4. Set **Token** to `{{access_token}}`.
5. Select **Send**.

Postman then sends the header `Authorization: Bearer <token>`.

| Scenario | Authorization tab |
| --- | --- |
| TC-11, TC-15, TC-17, TC-18, TC-19 | **Bearer Token**, with `{{access_token}}` |
| TC-12, TC-20 | **No Auth** |
| TC-13, TC-16 | **Bearer Token**, with `not-a-valid-token` |
| TC-14 | **Bearer Token**, with the expired token pasted in |

### Example requests

Register, `POST {{base_url}}/api/auth/register`:

```json
{
  "full_name": "Test User",
  "email": "manual.test@example.com",
  "password": "Test!Pass123",
  "confirm_password": "Test!Pass123"
}
```

Change password, `POST {{base_url}}/api/auth/change-password`:

```json
{
  "current_password": "Test!Pass123",
  "new_password": "New!Pass456",
  "confirm_new_password": "New!Pass456"
}
```

`POST {{base_url}}/api/auth/verify-token` has no body. It needs only the Bearer token.

## Known limitations

- **Existing tokens survive a password change:** in TC-17, a token issued before the change keeps working until it expires. See the [API documentation](04_API_Documentation.md).
- **No rate limiting:** these scenarios do not test repeated attempts, because no limit exists yet.

## Screenshots

The Swagger UI screenshots and a summary of these results are in the [screenshots folder](screenshots/README.md). There are no Postman application screenshots, because the application was not used.
