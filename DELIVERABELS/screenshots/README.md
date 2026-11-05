# Evidence Screenshots

All 11 images were captured on 5 November 2026 from a running stack, with both containers healthy. Each image was checked after capture, and none shows a whole access token, a password hash, a real secret, or the contents of `.env`. All credentials shown are dummy values.

| Done | File | Shows | How it was captured |
| --- | --- | --- | --- |
| [x] | [`01_project_structure.png`](01_project_structure.png) | Project folder structure | Command output: the files Git would upload, shown as a tree |
| [x] | [`02_docker_containers.png`](02_docker_containers.png) | Both containers healthy | Command output: `docker compose ps` |
| [x] | [`03_mysql_users_table.png`](03_mysql_users_table.png) | MySQL database and users table | Command output: SQL inside `auth-mysql`, leaving out the hash column |
| [x] | [`04_register_success.png`](04_register_success.png) | Successful registration, 201 | Swagger UI in Edge |
| [x] | [`05_login_success.png`](05_login_success.png) | Successful login, 200 | Swagger UI in Edge, token redacted |
| [x] | [`06_jwt_token_redacted.png`](06_jwt_token_redacted.png) | JWT token response | Swagger UI in Edge, token redacted |
| [x] | [`07_current_user.png`](07_current_user.png) | Current-user API response, 200 | Swagger UI in Edge |
| [x] | [`08_verify_token.png`](08_verify_token.png) | Verify-token API response, `"valid": true` | Swagger UI in Edge |
| [x] | [`09_change_password.png`](09_change_password.png) | Change-password API response, 200 | Swagger UI in Edge |
| [x] | [`10_swagger_ui.png`](10_swagger_ui.png) | Swagger UI, with every endpoint and **Authorize** | Swagger UI in Edge |
| [x] | [`11_api_test_results.png`](11_api_test_results.png) | Successful API testing results | Command output, plus the totals of the Swagger UI and Newman runs |

## How these images differ from hand-taken screenshots

- **Swagger UI images (04 to 10):** a script operated the real page in Microsoft Edge and saved the images. No person operated the browser. The script hid Swagger UI's `curl` text and the documented response examples to keep the images readable, and replaced each token with `eyJ...[TOKEN REDACTED]` before saving.
- **Command output images (01, 02, 03, and 11):** these show real command output, drawn as an image by a script. They are not screenshots of the desktop, VS Code, or a terminal window, and each one says so at the bottom.
- **Image 01:** it lists the files Git would upload, so `.env`, `.venv`, and caches are left out on purpose.
- **Image 11:** the Swagger UI and Newman lines are totals from those runs, not those tools' own output. The [API testing report](../07_API_Testing_Report.md) has the result of each scenario.
- **Postman:** no image shows the Postman application, because it is not installed on this machine and was not used.

## If you need to capture them again

If your reviewer needs screenshots taken by hand, start the stack with `docker compose up -d --build --wait`. Before saving each image, check that it shows no whole token, real password, secret, password hash, or `.env` contents. In Swagger UI, the `curl` text also contains the token.

To open MySQL, run this command. It asks for the root password from `.env`:

```powershell
docker compose exec auth-mysql mysql -u root -p shopease_auth_db
```

Then run these commands, which leave out the `password_hash` column:

```sql
SHOW TABLES;
DESCRIBE users;
SELECT id, full_name, email, role, is_active FROM users;
exit
```

To stop the stack afterwards, and delete its test data, run `docker compose down -v`.
