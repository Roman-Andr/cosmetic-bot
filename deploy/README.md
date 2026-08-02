# Production deployment

Production runs from immutable GHCR image digests. The server does not contain a Git checkout and
the deployment identity cannot execute an interactive shell or arbitrary Docker commands.

## Server-owned files

Install the audited files with root ownership:

- `compose.production.yml` as `/srv/cosmetic-bot/compose.yml`;
- `Caddyfile` as `/srv/cosmetic-bot/Caddyfile`;
- `cosmetic-deploy` as `/usr/local/sbin/cosmetic-deploy`, mode `0755`;
- application settings as `/etc/cosmetic-bot/app.env`, mode `0600`;
- Google credentials as `/etc/cosmetic-bot/secrets/google-service-account.json`, mode `0600`;
- Hysteria client config as `/etc/cosmetic-bot/secrets/hysteria.yaml`, mode `0600`.

The Hysteria config must listen on `0.0.0.0:1080` inside its isolated Compose network. Compose does
not publish that port to the host. The backend uses `TELEGRAM_PROXY_URL=socks5://hysteria:1080`.

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

## TLS and backups

Caddy obtains and renews the Let's Encrypt certificate automatically. Its `/data` and `/config`
directories use persistent volumes. Only ports 80 and 443 are published by Compose.

The backup service keeps daily PostgreSQL dumps for 180 days. Every deployment also stores a
pre-migration custom-format dump under `/srv/cosmetic-bot/backups`; copy backups to independent
storage and periodically test restoration.
