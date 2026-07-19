"""
One-time interactive script to regenerate config/token.json with a
fresh consent flow covering all four required scopes at once.

Run this directly (not via call_tool) — it opens a browser window
for you to log in and approve access.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

from app.core.config import settings
from app.core.google_auth import REQUIRED_SCOPES

flow = InstalledAppFlow.from_client_secrets_file(
    str(settings.google_credentials_path),
    REQUIRED_SCOPES,
)

creds = flow.run_local_server(port=0)

with open(settings.google_token_path, "w") as f:
    f.write(creds.to_json())

print("New token.json written successfully.")
print("Scopes granted:", creds.scopes)