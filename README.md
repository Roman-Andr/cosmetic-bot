# Velina Cosmetic Bot

Production-oriented Telegram bot and Mini App for the Velina Cosmetic loyalty
programme. The legacy product deep links and owner support chat remain available;
the new system records loyalty purchases in PostgreSQL and offers a customer Mini App.

## What is included

- configurable all-time turnover tiers (initially `0 → 3%`, `1000 → 5%`,
  `2000 → 7%`);
- a birthday promotion: a configurable 10% cashback overrides the tier rate from
  three calendar days before through three calendar days after the birthday;
- one-hour, one-use six-digit customer codes, stored only as HMAC digests;
- automatic bonus redemption capped at 10% of the full order and cashback on the
  cash-paid remainder;
- bonus expiry: every accrual stays spendable for `BONUS_LIFETIME_MONTHS` (default 6)
  through the same Minsk calendar day, purchases spend the soonest-expiring bonuses
  first, and customers are reminded 14, 7 and 1 day before bonuses burn;
- owner promotion campaigns in the Mini App: a scheduled broadcast to every customer
  with optional picture and optional gift bonuses that expire on their own date;
- an automatic birthday-cashback announcement on the first day of the birthday window;
- immutable purchase and bonus ledger, optional multi-product catalogue selection,
  reliable customer notifications through an outbox;
- owner/sales roles, owner search, XLSX exports, dashboard statistics and audit log;
- sales workspace in the Mini App and `/sale` in the bot use the same purchase
  preview and confirmation service; owner configuration is available in both
  the Mini App and bot commands (`/stats`, `/find`, `/admins`, `/addsales`,
  `/tiers`, `/exportcustomers`, `/exportpurchases`);
- customer-visible immutable bonus ledger and tier-progress data for the Mini App;
- Google Sheets catalogue synchronization, support-chat block/unblock controls;
- FastAPI API, React/Vite Telegram Mini App, PostgreSQL, Redis, Caddy HTTPS,
  daily backup configuration with 180-day retention.

## Local development

1. Install Python 3.14+ and [uv](https://docs.astral.sh/uv/).
2. Copy the environment template and replace every placeholder secret:

   ```bash
   cp .env.example .env
   ```

3. Install the locked dependency set and run quality checks:

   ```bash
   uv sync --group dev
   uv run ruff check app tests
   uv run ruff format --check app tests
   uv run mypy app
   uv run pytest
   ```

4. For the Mini App:

   ```bash
   cd frontend
   bun install --frozen-lockfile
   bun run dev
   ```

The Mini App requires Telegram `initData`; it deliberately does not authenticate
in a regular browser.

For a local test bot, set `APP_ENV=development` and `TELEGRAM_MODE=polling` in
your ignored `.env`. Production also uses polling, through the Hysteria proxy,
because inbound webhook connections from Telegram are blocked on the production
network; see [`deploy/README.md`](deploy/README.md).

## Production preparation

No server deployment is performed by this repository or its CI automatically.

1. Create a deployment-only `.env` from `.env.example`. Generate long random
   values for `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `WEBHOOK_SECRET`, and
   `LOYALTY_CODE_PEPPER`; never reuse the bot token as another secret.
2. Place the Google service-account JSON outside the repository and set
   `GOOGLE_SHEETS_CREDENTIALS_FILE_HOST` to that absolute host path. Its in-container
   counterpart remains `/run/secrets/google-service-account.json`.
3. Point `romanandr.ru` and `www.romanandr.ru` as appropriate to the host before
   starting Caddy; set `DOMAIN` and `ACME_EMAIL`.
4. Verify the manifest without starting services:

   ```bash
   ENV_FILE=.env docker compose config --quiet
   ```

5. The compose stack has an explicit migration service, internal-only PostgreSQL
   and Redis, automatic TLS via Caddy, and daily PostgreSQL backups retained for
   180 days in the `postgres-backups` Docker volume. Copy that volume to independent
   storage as part of operational disaster-recovery policy.

The CI workflow publishes backend, frontend, and Hysteria images to GHCR only after all backend,
frontend, and container checks pass on `master`. It deploys exact attested image digests through a
protected GitHub `production` environment and a forced-command SSH key. Application secrets remain
only on the server. See [`deploy/README.md`](deploy/README.md) for provisioning, rollback, VPN, TLS,
and backup details.

## Data and security notes

- `.env`, credential JSON files, keys, backups and runtime state are ignored by Git.
- Rotate any Telegram token or service-account key that was ever committed before
  using this public repository.
- Purchase corrections and returns are intentionally out of scope for the first
  release: confirmed purchases are immutable and do not alter loyalty balances.
- Launched campaigns cannot be revoked: gift bonuses are ordinary immutable ledger
  credits. A campaign can only be edited or cancelled while it is still scheduled.
  While its gift bonuses are still valid, a launched campaign can be sent to customers
  who registered after the launch; each account receives a campaign's gift at most once.
