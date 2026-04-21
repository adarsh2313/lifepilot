"""One-time OAuth2 flow for Google Calendar API.

Usage (run once from terminal):
    conda activate lifepilot
    python -m backend.calendar.auth

This opens a browser, asks you to approve Calendar access, then saves
credentials to  <project_root>/google_credentials.json  (token only —
the OAuth client secrets are read from  <project_root>/google_client_secret.json).

After running this once, the backend reads the token automatically and
refreshes it silently when it expires.

Setup steps (one time):
1.  Go to https://console.cloud.google.com/
2.  Create a project (or pick existing)
3.  Enable "Google Calendar API"
4.  Create credentials → OAuth 2.0 Client ID → Desktop app
5.  Download the JSON → save as  <project_root>/google_client_secret.json
6.  Run this script: python -m backend.calendar.auth
"""

import json
import sys
import webbrowser
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

PROJECT_DIR   = Path(__file__).resolve().parent.parent.parent
CLIENT_SECRET = PROJECT_DIR / "google_client_secret.json"
TOKEN_FILE    = PROJECT_DIR / "google_credentials.json"


def run_auth_flow() -> Credentials:
    if not CLIENT_SECRET.exists():
        print(f"\n[ERROR] Client secret not found at:\n  {CLIENT_SECRET}")
        print("\nSteps:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Enable Google Calendar API")
        print("  3. Create OAuth 2.0 Client ID (Desktop app)")
        print("  4. Download JSON → save as google_client_secret.json in project root")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    TOKEN_FILE.write_text(creds.to_json())
    print(f"\n[OK] Credentials saved to:\n  {TOKEN_FILE}")
    return creds


def load_credentials() -> Credentials:
    """Load stored credentials, refreshing if expired. Raises if not authorised."""
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "Google Calendar not authorised. Run:  python -m backend.calendar.auth"
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return creds


if __name__ == "__main__":
    run_auth_flow()
