# Repository Guidelines

## Project Structure & Module Organization

Backend code lives in `app/`: HTTP endpoints in `app/api/routes/`, Telegram behavior in `app/bot/`, business rules in `app/services/`, persistence in `app/models/` and `app/db/`, and API types in `app/schemas/`. `app/main.py` assembles FastAPI and background tasks. Database revisions belong in `alembic/versions/`; backend tests live in `tests/`.

The Mini App is under `frontend/`. Follow its feature-oriented layout: primitives in `src/shared/`, domain types in `src/entities/`, flows in `src/features/`, and composed screens in `src/widgets/`. Deployment assets are at the root and in `.github/workflows/`.

## Build, Test, and Development Commands

- `uv sync --locked --group dev` installs the locked Python dependencies.
- `uv run cosmetic-api` starts the backend; configure an ignored `.env` first.
- `uv run ruff check app tests && uv run ruff format --check app tests` runs Python lint and format checks.
- `uv run mypy app && uv run pytest` runs strict typing and backend tests.
- `cd frontend && bun install --frozen-lockfile && bun run dev` installs the locked frontend dependencies and starts Vite.
- `cd frontend && bun run lint && bun run test && bun run build` reproduces frontend CI checks.
- `ENV_FILE=.env docker compose config --quiet` validates the stack configuration; `docker compose up --build` builds and starts all services.

## Temporary HTTPS for Local Mini App Testing

Telegram Mini Apps require a public HTTPS URL. With the local Compose stack running and
`DOMAIN=localhost` in the ignored `.env`, start an account-less Cloudflare Quick Tunnel in a
detached container:

```bash
docker run -d --name cosmetic-bot-cloudflared --network host \
  cloudflare/cloudflared:latest tunnel --no-autoupdate \
  --url https://127.0.0.1:443 \
  --no-tls-verify \
  --origin-server-name localhost \
  --http-host-header localhost
```

Both `--origin-server-name localhost` and `--http-host-header localhost` are required because
Caddy serves a locally issued certificate and site for `localhost`; omitting the TLS server name
causes the public endpoint to return `502 Bad Gateway`. Read the generated URL from:

```bash
docker logs cosmetic-bot-cloudflared
```

It has the form `https://<random-words>.trycloudflare.com`. Put the actual address into a shell
variable and verify the complete public route, not just the tunnel process:

```bash
TUNNEL_URL='https://replace-with-the-generated-name.trycloudflare.com'
curl "$TUNNEL_URL/api/health/ready"
```

Set that URL as `PUBLIC_BASE_URL` in `.env`, then apply it without unnecessarily recreating the
database and cache containers:

```bash
docker compose up -d --no-deps --force-recreate backend
docker compose ps backend
docker compose logs --tail=30 backend
```

The endpoint must return HTTP 200, and the backend must become healthy before handing the URL off.
Ask the Telegram user to run `/start` again so newly generated Mini App buttons use the current
URL. Quick Tunnel URLs have no uptime guarantee and remain temporary: recreating the container
generates a new URL, which requires repeating the `.env` update and backend restart. If the named
container already exists and a fresh tunnel is required, remove only that exact container with
`docker rm -f cosmetic-bot-cloudflared` before starting it again.

## Coding Style & Naming Conventions

Use four-space indentation and 100-character lines for Python. Ruff enforces imports and Python 3.12 syntax; mypy is strict. Use `snake_case` for modules/functions, `PascalCase` for classes, and annotations on new code. TypeScript uses two-space indentation, `PascalCase` components, `camelCase` functions, and shared domain types. ESLint is authoritative.

## Testing Guidelines

Pytest discovers `tests/test_*.py`; name tests `test_<behavior>` and cover success, validation, authorization, and boundaries. Add regression tests with bug fixes and service-level tests for loyalty or ledger changes. No numeric coverage threshold is configured; changed behavior must be exercised.

## Commit & Pull Request Guidelines

Follow the history’s short, imperative subjects, such as `Add birthday cashback`; omit trailing punctuation and keep each commit focused. PRs should explain scope and user impact, call out migrations or configuration changes, link relevant issues, and include Mini App screenshots for visual changes. Report the backend and frontend checks run.

## Security & Data Integrity

Never commit `.env`, Telegram tokens, service-account JSON, database dumps, or production data. Validate Telegram Mini App `initData` server-side. Preserve owner/sales role boundaries, idempotent purchase handling, and immutable purchase/bonus ledgers; introduce schema changes only through Alembic migrations.
