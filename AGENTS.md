# Repository Guidelines

## Project

Velina Cosmetic Bot: a Telegram bot + Mini App implementing a loyalty/cashback programme, backed
by FastAPI, PostgreSQL, and Redis. The bot and the Mini App API are the same ASGI process
(`app/main.py`); there is no separate bot process. A React/Vite Mini App is served behind Caddy at
the same domain, proxied to the API under `/api`.

## Project Structure & Module Organization

Backend code lives in `app/`: HTTP endpoints in `app/api/routes/`, Telegram behavior in `app/bot/`, business rules in `app/services/`, persistence in `app/models/` and `app/db/`, and API types in `app/schemas/`. `app/main.py` assembles FastAPI and background tasks. Database revisions belong in `alembic/versions/`; backend tests live in `tests/`.

The Mini App is under `frontend/`. Follow its feature-oriented layout: primitives in `src/shared/`, domain types in `src/entities/`, flows in `src/features/`, and composed screens in `src/widgets/`. Deployment assets are at the root and in `.github/workflows/`.

## Architecture

### Backend layout (`app/`)

- `app/main.py` — the single FastAPI app. `lifespan()` seeds default data and starts four
  background `asyncio` tasks that live for the process lifetime: catalogue sync from Google
  Sheets, the Telegram runtime (`run_telegram`), the notification outbox delivery loop, and the
  health monitor loop. A single `Bot` and `Dispatcher` are constructed once at import time and
  reused everywhere (webhook route, polling, notifications).
- `app/api/routes/` — HTTP routers: `loyalty.py` (customer-facing Mini App endpoints, e.g.
  `/api/loyalty/*`), `admin.py` (owner/sales endpoints, e.g. `/api/admin/*`), `health.py`.
- `app/api/dependencies.py` — auth chain for HTTP requests: `X-Telegram-Init-Data` header →
  `validate_init_data` (HMAC-verified against the bot token) → `TelegramIdentity` →
  `CustomerDependency`/`SalesAdminDependency`/`OwnerDependency`. Role checks are simple dependency
  layering: `OwnerDependency` depends on `SalesAdminDependency`.
- `app/bot/` — aiogram side. `application.py` builds the `Bot`/`Dispatcher` (Redis-backed FSM
  storage so sale drafts survive restarts) and the webhook route (`/api/telegram/webhook`,
  protected by a secret header compared with `hmac.compare_digest`). `routers/` split bot commands
  by audience: `access.py` (entry gating), `customer.py`, `owner.py`, `sales.py`, `support.py`.
  `states.py` defines the aiogram FSM states (`SaleStates`, `OwnerStates`).
- `app/services/` — business logic, framework-agnostic w.r.t. FastAPI/aiogram:
  - `loyalty.py` — the core transactional engine (`LoyaltyService`). Purchase recording, bonus
    redemption/accrual, tier lookup, and the birthday-cashback override all live here. Both the
    bot's `/sale` flow and the Mini App's sales workspace call the *same* `LoyaltyService` methods
    (`preview_purchase`, `record_purchase`, `lookup_buyer`) so the two surfaces can never diverge
    on money math.
  - `tier_rules.py` — owner-configurable turnover tiers.
  - `customer_data.py` / `customer_search.py` — phone normalization/masking and owner customer
    search.
  - `telegram_auth.py` — standalone Mini App `initData` HMAC validation (used by
    `api/dependencies.py`).
  - `monitoring.py` — background health checks (disk, backup freshness, Redis) with Telegram
    alerting to the owner; explicitly cannot detect a fully dead process, see its module docstring.
  - `reports.py` — XLSX export generation for owner downloads.
  - `bootstrap.py` — first-run seeding of default settings (called from `lifespan`).
- `app/models/domain.py` — all SQLAlchemy ORM models in one module. Money uses `Numeric(12, 2)`
  (`MONEY`), percentages `Numeric(5, 2)` (`PERCENT`). Purchases and bonus transactions are
  append-only/immutable by design (see Domain invariants below).
- `app/schemas/` — Pydantic request/response models, split `admin.py` / `loyalty.py`.
- `app/db/` — `session.py` (async engine/sessionmaker, `get_session` dependency), `base.py`
  (declarative `Base`, `CreatedAtMixin`).
- `app/core/config.py` — single `pydantic-settings` `Settings` class, all env vars, cached via
  `get_settings()`. This is the source of truth for every configuration key (also mirrored in
  `.env.example`).

### Database migrations

Alembic, files under `alembic/versions/` named `YYYYMMDD_NNNN_description.py` with an explicit
`revision`/`down_revision` chain (no branching). All schema changes go through a new migration —
never hand-edit models without a matching migration.

### Domain invariants (money/loyalty correctness)

These are load-bearing and enforced by `LoyaltyService` + DB check constraints, not just
convention:

- Confirmed purchases and bonus transactions are immutable/append-only — no edit or delete path
  exists for either (`PurchaseStatus` only has `CONFIRMED`; see README "Data and security notes").
  Corrections/returns are explicitly out of scope for v1.
- Bonus redemption is capped at 10% of the purchase total (`MAX_BONUS_SHARE`); cashback accrues
  only on the cash-paid remainder, never on the redeemed portion.
- Birthday cashback (`effective_cashback`) overrides the tier rate for an inclusive window
  (`birthday_cashback_window_days`, default ±3 calendar days) around the observed birthday, with
  29 Feb observed as 28 Feb in non-leap years; window checks are done against local Minsk calendar
  dates (`MINSK_TIMEZONE`), not UTC.
- All monetary values pass through `money()` (`ROUND_HALF_UP`, 2 decimal places) except the bonus
  cap itself, which truncates (`ROUND_DOWN`).
- Six-digit customer codes are one-hour, single-use, and stored only as an HMAC-SHA256 digest
  (`code_digest`, keyed by `LOYALTY_CODE_PEPPER`) — the plaintext code is never persisted.
  Generating a new code invalidates the account's previous unused code.
- Row-level locking (`SELECT ... FOR UPDATE`) on the loyalty account and code rows makes
  concurrent code redemption/purchase confirmation race-safe; mutating operations in
  `LoyaltyService` explicitly commit/rollback around a `try/except`.
- Customer-facing notifications are written to `NotificationOutbox` in the *same* transaction as
  the purchase, then delivered asynchronously by `notification_delivery_loop` — never sent
  synchronously from inside the request/update handler.

### Frontend layout (`frontend/src/`)

Feature-Sliced Design:

- `shared/` — framework primitives: `api/client.ts` (fetch wrapper that attaches
  `X-Telegram-Init-Data` from `window.Telegram.WebApp.initData` to every request; throws `ApiError`
  on non-2xx), `api/queryClient.ts`, UI atoms (`Modal`, `Money`, `Icon`, `SectionTile`), `lib/`
  helpers (`telegram.ts`, `format.ts`, debounce, error-notice hook).
- `entities/` — domain types + React Query hooks per bounded domain: `admin/`, `catalog/`,
  `loyalty/` (each with `api/queries.ts`, `api/mutations.ts`, `model/types.ts`).
- `features/` — one interactive flow per folder, e.g. `sale/` (the sales workspace shared in
  intent with the bot's `/sale` FSM), `registration/`, `loyalty-code/`, `bonus-history/`,
  `purchase-history/`, `tier-progress/`, `administrator-management/`, `customer-management/`,
  `birthday/`.
- `widgets/` — composed screens: `admin/OwnerDashboard.tsx`, `profile/ProfilePanel.tsx`.
- `app/App.tsx` — root composition and providers (`QueryProvider`).

The API base path is always `/api/...`; Caddy is the only thing that puts frontend and backend on
one origin, so during `bun run dev` the Vite dev server must be reached through the same tunnel/
proxy setup described below under "Temporary HTTPS for Local Mini App Testing", not opened
directly in a bare browser tab.

## Build, Test, and Development Commands

- `uv sync --locked --group dev` installs the locked Python dependencies.
- `uv run cosmetic-api` starts the backend; configure an ignored `.env` first.
- `uv run ruff check app tests && uv run ruff format --check app tests` runs Python lint and format checks.
- `uv run mypy app && uv run pytest` runs strict typing and backend tests.
- `uv run pytest tests/test_loyalty_math.py -k test_redemption_is_capped` runs a single test.
- `cd frontend && bun install --frozen-lockfile && bun run dev` installs the locked frontend dependencies and starts Vite.
- `cd frontend && bun run lint && bun run test && bun run build` reproduces frontend CI checks.
- `cp .env.example .env` then fill in every placeholder secret before running the stack.
- `ENV_FILE=.env docker compose config --quiet` validates the stack configuration; `docker compose up --build` builds and starts all services (postgres, redis, migrate, backend, frontend, caddy, backup).

Set `APP_ENV=development` and `TELEGRAM_MODE=polling` in `.env` for local bot testing with a test
token; `TELEGRAM_MODE=webhook` is required in production.

CI (`.github/workflows/ci.yml`) runs backend checks, frontend checks, then a container build job,
then (on `master` only) publishes attested GHCR images and deploys via SSH to a protected
`production` environment. Nothing deploys automatically from a local machine or from PRs.

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

Never push directly to `master`. Push work to a branch, open a PR, and merge through GitHub (`gh pr create` / `gh pr merge`) so CI runs and the change is reviewable.

## Security & Data Integrity

Never commit `.env`, Telegram tokens, service-account JSON, database dumps, or production data. Validate Telegram Mini App `initData` server-side. Preserve owner/sales role boundaries, idempotent purchase handling, and immutable purchase/bonus ledgers; introduce schema changes only through Alembic migrations.
