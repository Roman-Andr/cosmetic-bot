## Summary

<!-- What changed and why, in a sentence or two. -->

## User / operational impact

<!-- What does this change for customers, sales staff, the owner, or on-call? "None" is fine. -->

## Migrations & configuration

- [ ] This PR includes an Alembic migration (`alembic/versions/`) — describe the schema change and whether it's backward-compatible with the currently deployed app version.
- [ ] This PR adds/changes an environment variable — updated in `app/core/config.py` and `.env.example`.
- [ ] Neither applies.

## Screenshots

<!-- Required for Mini App (frontend/) visual changes. Delete this section otherwise. -->

## Checks run

- [ ] `uv run ruff check app tests && uv run ruff format --check app tests`
- [ ] `uv run mypy app`
- [ ] `uv run pytest`
- [ ] `cd frontend && bun run lint && bun run test && bun run build`
- [ ] N/A — explain why (e.g. docs-only change)

## Related issues

<!-- Link relevant issues, e.g. Closes #123 -->
