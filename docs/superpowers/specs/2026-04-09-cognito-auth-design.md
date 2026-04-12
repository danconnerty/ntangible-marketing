# AWS Cognito Authentication for Control Room

Replace the built-in username/password auth with AWS Cognito, giving each team member their own login with secure password handling, brute force protection, and self-service password reset.

## Decision Summary

- **Provider**: AWS Cognito (Hosted UI)
- **Login flow**: Redirect to Cognito → authenticate → redirect back with auth code
- **User management**: Admin creates users in Cognito console, users get temp password by email
- **MFA**: Disabled (can be enabled later)
- **Roles**: None — all users have equal access
- **Session**: JWT tokens stored in secure cookie, 1-hour expiry with 30-day refresh

## Login Flow

1. User opens `/control-room` (any protected route)
2. Middleware checks for valid session cookie
3. If no valid session: redirect to Cognito Hosted UI
4. User logs in on Cognito's page (email + password)
5. Cognito redirects to `/control-room/auth/callback?code=...`
6. App exchanges auth code for JWT tokens (ID token + access token + refresh token)
7. App stores tokens in a secure HTTP-only session cookie
8. User sees the dashboard
9. On subsequent requests, middleware validates the JWT from the cookie
10. When token expires (1 hour), app uses refresh token to get a new one silently
11. After 30 days, user must log in again

## AWS Resources

### Cognito User Pool: `ntangible-marketing-users`

- **Region**: us-east-2 (same as Lightsail)
- **Username**: email address
- **Password policy**: 8+ characters, requires uppercase + number
- **Email verification**: enabled (Cognito sends verification email)
- **MFA**: off
- **Account recovery**: email-based password reset

### App Client: `ntangible-control-room`

- **Callback URL**: `http://3.21.46.13/control-room/auth/callback`
- **Sign-out URL**: `http://3.21.46.13/control-room`
- **OAuth flows**: Authorization code grant
- **Scopes**: openid, email, profile
- **Client secret**: generated (stored in .env)

### Cognito Domain

- **Domain**: `ntangible-marketing` (hosted at `ntangible-marketing.auth.us-east-2.amazoncognito.com`)

## Code Changes

### New dependencies (`pyproject.toml`)

Add `pyjwt[crypto]>=2.0.0` for JWT token validation.

### Configuration (`app/config.py`)

Remove:
- `control_room_username`
- `control_room_password`
- `control_room_session_secret`

Add:
- `cognito_user_pool_id` — e.g. `us-east-2_xxxxxxxx`
- `cognito_client_id` — app client ID
- `cognito_client_secret` — app client secret
- `cognito_domain` — e.g. `ntangible-marketing.auth.us-east-2.amazoncognito.com`
- `cognito_redirect_uri` — `http://3.21.46.13/control-room/auth/callback`

Keep:
- `control_room_require_auth` — still useful as a toggle
- `api_key` — unchanged, used for programmatic API access

### Auth module (`app/auth.py`)

Replace the existing session/password functions with:
- `get_cognito_login_url()` — builds the Cognito Hosted UI URL with proper params
- `exchange_code_for_tokens(code)` — POST to Cognito token endpoint, returns JWT tokens
- `validate_cognito_token(token)` — validates JWT signature against Cognito's public keys (JWKS)
- `refresh_cognito_token(refresh_token)` — uses refresh token to get new ID/access tokens
- `get_current_user(request)` — reads session cookie, validates token, returns user email

Keep:
- `verify_api_key()` — unchanged
- `CONTROL_ROOM_SESSION_COOKIE` — reuse cookie name

### Middleware (`app/main.py`)

Update the control room middleware to:
1. Skip auth for `/control-room/login`, `/control-room/auth/callback`, `/static/`
2. Check session cookie for valid JWT
3. If token expired, try silent refresh
4. If no valid session and no refresh possible, redirect to Cognito login

### Web routes (`app/web/routes.py`)

Replace:
- `GET /control-room/login` — now redirects to Cognito Hosted UI (no template needed)
- `POST /control-room/login` — remove (Cognito handles form submission)

Add:
- `GET /control-room/auth/callback` — receives auth code from Cognito, exchanges for tokens, sets cookie, redirects to dashboard
- `GET /control-room/logout` — clears session cookie and redirects to Cognito logout URL

Remove:
- `login.html` template

### Environment (`.env`)

Add:
```
COGNITO_USER_POOL_ID=us-east-2_xxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_DOMAIN=ntangible-marketing.auth.us-east-2.amazoncognito.com
COGNITO_REDIRECT_URI=http://3.21.46.13/control-room/auth/callback
```

### Test config (`tests/conftest.py`)

Add test defaults for Cognito env vars. Tests that hit the control room will mock the JWT validation.

## What Does NOT Change

- API key auth for `/api/*` routes
- Dashboard templates and functionality
- Scheduler, agents, publishers
- Database schema (no new tables needed — user data lives in Cognito)

## Adding Team Members

1. Go to AWS Console → Cognito → User Pools → `ntangible-marketing-users`
2. Click "Create user"
3. Enter their email address
4. They receive an email with a temporary password
5. On first login, they set their own password
