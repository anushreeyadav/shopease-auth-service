# Teams Progress Updates

Copy the template below for each day, newest entry first, then paste the completed entry into Teams.

## Template

```text
Date:
Project: ShopEase Auth Service

Completed today:
-

In progress:
-

Blockers:
- None

Plan for tomorrow:
-
```

## Updates

### 5 November 2026

```text
Date: 5 November 2026
Project: ShopEase Auth Service

Completed today:
- Dockerized the service with auth-service and auth-mysql. Both containers start healthy, and the application connects to MySQL.
- Ran the 22 mandatory API scenarios on Docker and MySQL: 22 of 22 passed.
- Completed the final code and security audit: all checks passed, including token expiry, inactive users, and secret scans.
- Automated tests: 299 passed, 0 failed.
- Ran the same 22 scenarios through Swagger UI in a browser using a script, and from a Postman collection using Newman: 22 of 22 passed on each.
- Captured the evidence screenshots, with tokens redacted.
- Completed the README, the final completion report, and the Postman collection.

In progress:
- Nothing. Implementation and testing are complete.

Blockers:
- None

Plan for tomorrow:
- Review the project, then commit and push it to GitHub.
```

### 4 November 2026: Day 2 work

```text
Date: 4 November 2026
Project: ShopEase Auth Service

Completed today:
- Implemented the current user, verify token, and change password APIs.
- Reviewed the complete application: routes, Swagger UI, Bearer authentication, error handling, and status codes.
- Tested the complete application against MySQL 8.4.11.
- Automated tests: 276 passed, 0 failed.
- Completed the API documentation.

In progress:
- Docker execution and API testing report.

Blockers:
- None

Plan for tomorrow:
- Run the complete Docker stack and the API test scenarios.
```

### 4 November 2026: Day 1 work

```text
Date: 4 November 2026
Project: ShopEase Auth Service

Completed today:
- Created the Authentication Microservice project and secure environment settings.
- Implemented the MySQL users table and Alembic migrations.
- Implemented password hashing, JWT handling, and the registration and login APIs.
- Automated tests: 155 passed, 0 failed.

In progress:
- Protected user APIs.

Blockers:
- None

Plan for tomorrow:
- Implement the current user, verify token, and change password APIs.
```

