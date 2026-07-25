# Velina Cosmetic Bot

Production-oriented Telegram bot and Mini App for the Velina Cosmetic loyalty
programme. The legacy product deep links and owner support chat remain available;
the new system records loyalty purchases in PostgreSQL and offers a customer Mini App.

## What is included

- configurable all-time turnover tiers (initially `0 → 3%`, `1000 → 5%`,
  `2000 → 7%`);
- one-hour, one-use six-digit customer codes, stored only as HMAC digests;
- automatic bonus redemption capped at 10% of the full order and cashback on the
  cash-paid remainder;
- immutable purchase and bonus ledger, optional multi-product catalogue selection,
  reliable customer notifications through an outbox;
- owner/sales roles, owner search, XLSX exports, dashboard statistics and audit log;
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
   npm ci
   npm run dev
   ```

The Mini App requires Telegram `initData`; it deliberately does not authenticate
in a regular browser.

For a local test bot, set `APP_ENV=development` and `TELEGRAM_MODE=polling` in
your ignored `.env`. Polling never registers a public webhook and is intended
only for a test token. The production configuration must use `TELEGRAM_MODE=webhook`.

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

The `Publish images` GitHub workflow pushes validated backend and frontend images
to GHCR only on `master`. Its deployment job is manual and protected by the
GitHub `production` environment; it will not run until that environment and its
deployment secrets are configured.

## Privacy launch blocker

The currently linked policy is https://velinacosmetic.by/privacy. Before public
launch it must explicitly cover Telegram account identifiers, date of birth,
gender, loyalty balances/purchases, processing purposes, retention and customer
rights. The Mini App already requires an affirmative link-based consent, but the
policy text itself has intentionally not been changed in this repository.

## Data and security notes

- `.env`, credential JSON files, keys, backups and runtime state are ignored by Git.
- Rotate any Telegram token or service-account key that was ever committed before
  using this public repository.
- Purchase corrections and returns are intentionally out of scope for the first
  release: confirmed purchases are immutable and do not alter loyalty balances.
