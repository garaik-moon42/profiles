"""Google API authentication, service clients and request retry."""

import json
from pathlib import Path
import time

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

RENDERER_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = RENDERER_DIR.parents[1]
CREDENTIALS_PATH = RENDERER_DIR / "credentials.json"
OUTPUT_DIR = REPOSITORY_ROOT / "target" / "gdocs"
TOKEN_PATH = OUTPUT_DIR / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = (4, 8, 16, 32)  # ~60 s in total


def _saved_scopes_match():
    try:
        saved = json.loads(TOKEN_PATH.read_text(encoding="utf-8")).get("scopes")
    except (OSError, ValueError):
        return False
    return isinstance(saved, list) and set(saved) == set(SCOPES)


def authenticate():
    credentials = None
    if TOKEN_PATH.exists() and _saved_scopes_match():
        credentials = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except RefreshError:
            # Expired or revoked refresh token (e.g. 7-day limit in Testing mode).
            credentials = None
    if not credentials or not credentials.valid:
        if not CREDENTIALS_PATH.is_file():
            raise FileNotFoundError(
                f"Az OAuth klienskonfiguráció nem található: {CREDENTIALS_PATH}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        credentials = flow.run_local_server(port=0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")
    TOKEN_PATH.chmod(0o600)
    return credentials


def build_services(credentials):
    """Return (drive v3, docs v1, sheets v4) clients."""
    return tuple(
        build(name, version, credentials=credentials, cache_discovery=False)
        for name, version in (("drive", "v3"), ("docs", "v1"), ("sheets", "v4"))
    )


def execute(request):
    """Execute a googleapiclient request, retrying on 429/5xx."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            return request.execute()
        except HttpError as error:
            status = error.resp.status
            retryable = status == 429 or 500 <= status < 600
            if not retryable or attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(BACKOFF_SECONDS[attempt])
