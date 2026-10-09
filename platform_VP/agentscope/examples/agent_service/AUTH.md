# Local account authentication

The optional auth service uses:

- Argon2id password hashes;
- 15-minute HS256 JWT access tokens;
- opaque 30-day refresh tokens in an HttpOnly cookie;
- HMAC-SHA256 refresh-token hashes in PostgreSQL;
- one-time refresh rotation and token-family revocation on reuse.

When `AUTH_ENABLED=true`, existing business endpoints ignore `X-User-ID` and
require `Authorization: Bearer <access-token>`. When disabled, the legacy
header remains available for local examples.

## Configuration

Generate different signing and hashing secrets:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set them in `.env` and enable auth:

```dotenv
AUTH_ENABLED=true
AUTH_JWT_SECRET=<first-generated-value>
AUTH_REFRESH_PEPPER=<second-generated-value>
AUTH_DEFAULT_TENANT_ID=default
AUTH_COOKIE_SECURE=false
```

Use `AUTH_COOKIE_SECURE=true` behind production HTTPS.

## API lifecycle

Load valid registration choices first:

```http
GET /directory/domains
GET /directory/domains/vinhomes/areas
```

Register an `AREA_MANAGER` into the server-configured default tenant and one
validated area:

```http
POST /auth/register
Content-Type: application/json

{
  "email": "alice@example.com",
  "username": "alice",
  "password": "a-long-unique-password",
  "domain_id": "vinhomes",
  "area_id": "ocean-park-1"
}
```

The access token carries the fixed `AREA_MANAGER` role plus the selected
domain/area scope. See `../../docs/area_platform_api_vi.md` for domain partner
keys, ticket routing, and reviewed memory.

Login:

```http
POST /auth/login
Content-Type: application/json

{
  "tenant_id": "default",
  "identity": "alice@example.com",
  "password": "a-long-unique-password"
}
```

The response body contains the access token. The refresh token is never put in
JavaScript-visible storage; it is sent as an HttpOnly cookie scoped to `/auth`.

Use the access token:

```http
Authorization: Bearer <access-token>
```

Rotate the refresh token by sending the cookie to `POST /auth/refresh`. Reusing
an already-rotated token revokes every session in that token family. Use
`POST /auth/logout` for the current refresh session or `POST /auth/logout-all`
with an access token to revoke every refresh session for the account.

Already-issued access tokens are stateless and remain usable until their
15-minute expiry. Immediate access-token revocation would require an additional
denylist or token-version lookup on every request.

## Frontend status

The included Web UI supports registration and login. It keeps the short-lived
access token in memory, sends it as a Bearer token, rotates the HttpOnly refresh
cookie after reload or a 401 response, and never stores either token in
`localStorage`. Set `AUTH_ENABLED=true` and configure an explicit
`CORS_ALLOWED_ORIGINS` list when the UI and API use different origins.

