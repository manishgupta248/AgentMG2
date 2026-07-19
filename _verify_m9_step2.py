"""
M9 Step 2 verification: build each of the 4 Google service clients
and make one trivial real API call per service to confirm the OAuth
flow, token loading, and caching all work end-to-end.
"""

from app.core.google_auth import get_google_service

# Gmail — get the authenticated user's profile (trivial, read-only)
gmail = get_google_service("gmail")
profile = gmail.users().getProfile(userId="me").execute()
print("Gmail profile email:", profile.get("emailAddress"))

# Drive — list up to 3 files (trivial, read-only)
drive = get_google_service("drive")
files = drive.files().list(pageSize=3, fields="files(id, name)").execute()
print("Drive files (first 3):", [f["name"] for f in files.get("files", [])])

# Calendar — list calendars
calendar = get_google_service("calendar")
calendars = calendar.calendarList().list(maxResults=3).execute()
print("Calendars (first 3):", [c["summary"] for c in calendars.get("items", [])])

# Sheets — just confirm the client builds (no real spreadsheet ID handy yet)
sheets = get_google_service("sheets")
print("Sheets client built:", sheets is not None)

# Confirm caching works — calling again should return the SAME cached object
gmail2 = get_google_service("gmail")
print("Gmail client is cached (same object):", gmail is gmail2)
