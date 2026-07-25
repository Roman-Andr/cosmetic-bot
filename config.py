"""Legacy bot settings loaded from the environment.

Keep secrets in a local ``.env`` file or deployment secret store. Never commit
credentials to this module.
"""

from os import environ


def required(name: str) -> str:
    """Return a required environment variable with a clear startup error."""
    value = environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


API_TOKEN = required("API_TOKEN")
ADMIN_ID = int(required("ADMIN_ID"))
GOOGLE_SHEETS_CREDENTIALS_FILE = required("GOOGLE_SHEETS_CREDENTIALS_FILE")
GOOGLE_SHEET_NAME = required("GOOGLE_SHEET_NAME")
