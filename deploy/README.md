# Production deployment

Production runs from immutable GHCR image digests. The server does not contain a Git checkout and
the deployment identity cannot execute an interactive shell or arbitrary Docker commands.

## Server-owned files

Install the audited files with root ownership:

- `compose.production.yml` as `/srv/cosmetic-bot/compose.yml`;
- `Caddyfile` as `/srv/cosmetic-bot/Caddyfile`;
- `cosmetic-deploy` as `/usr/local/sbin/cosmetic-deploy`, mode `0755`;
- application settings as `/etc/cosmetic-bot/app.env`, mode `0600`.

`app.env` is read by the Docker CLI while composing, so root ownership is fine. The two secrets
below are bind-mounted directly into their container's filesystem and read by that container's own
unprivileged process, so they must be owned by the *container's* user, not `root`, or the container
fails with `permission denied`:

- Google credentials as `/etc/cosmetic-bot/secrets/google-service-account.json`, owned by `999:999`
  (the backend image's `app` user), mode `0400`;
- Hysteria client config as `/etc/cosmetic-bot/secrets/hysteria.yaml`, owned by `100:101`
  (the Hysteria image's `hysteria` user), mode `0400`.

The Hysteria config must listen on `0.0.0.0:1080` inside its isolated Compose network. Compose does
not publish that port to the host. The backend uses `TELEGRAM_PROXY_URL=socks5://hysteria:1080`.

`TELEGRAM_MODE` must stay `polling` on this host. Russian network filtering blocks inbound
connections from Telegram, so webhook delivery times out; the backend reaches Telegram outbound only
through the Hysteria proxy. Switching to `webhook` silently breaks the bot.

## Monitoring and alerts

The backend runs a background health monitor that checks PostgreSQL, Redis, Telegram reachability,
the age of the newest daily backup, and free disk (via the read-only `postgres-backups` mount, which
shares the data filesystem). It sends a Telegram message to `ALERT_TELEGRAM_ID` (falling back to
`OWNER_TELEGRAM_ID`) whenever a signal flips to unhealthy, and again when it recovers. This cannot
detect a fully dead process or host — add a free external dead-man-switch that pings
`https://romanandr.ru/api/health/ready` for that coverage.

## Restricted deployment identity

Create a `deploy` user with `/usr/sbin/nologin` and no Docker group membership. Its dedicated SSH
public key must use an `authorized_keys` forced command:

```text
restrict,command="sudo -n /usr/local/sbin/cosmetic-deploy" ssh-ed25519 AAAA... github-production-deploy
```

Preserve only OpenSSH's server-generated original command and allow the one root-owned script:

```text
Defaults:deploy env_keep += "SSH_ORIGINAL_COMMAND"
deploy ALL=(root) NOPASSWD: /usr/local/sbin/cosmetic-deploy
```

The script validates three OCI digests and one commit SHA. It receives the short-lived workflow
`GITHUB_TOKEN` on stdin, verifies GitHub build attestations, pulls exact digests, creates a database
backup, applies migrations, waits for container health, and verifies the public HTTPS readiness
route. If an application update fails, it restores the previous image references. Database restore
is deliberately not automatic.

## GitHub environment

Create a protected `production` environment restricted to `master` and add:

- `DEPLOY_HOST`;
- `DEPLOY_USER`;
- `DEPLOY_SSH_PRIVATE_KEY`;
- `DEPLOY_KNOWN_HOSTS`, captured and verified out of band.

The workflow runs CI before publishing, produces SBOM/provenance data, attaches GitHub
attestations, waits for production approval, and serializes deployments. Application, database,
Telegram, Google, and VPN secrets remain only on the server.

## Existing mox edge, TLS, and backups

The production host already runs the mox mail server on public ports 80 and 443. Mox terminates
TLS, obtains and renews the Let's Encrypt certificate for `romanandr.ru`, and forwards that host to
`http://localhost:3000`. Compose therefore publishes Caddy only on `127.0.0.1:3000`; Caddy handles
application routing but is not exposed publicly and must not compete with mox for ACME or edge
ports. Preserve the `romanandr_app` mox web handler when updating the mail server.

The backup service keeps daily PostgreSQL dumps for 180 days and, with `BACKUP_ON_START=TRUE`, also
takes one immediately on every start so a restart before midnight never skips a day. Every
deployment additionally stores a pre-migration custom-format dump under `/srv/cosmetic-bot/backups`;
the deploy script prunes those to the last 14. All of these dumps live on the server's single disk —
copy them to independent storage and periodically test restoration.
