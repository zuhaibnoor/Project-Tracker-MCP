"""
test_connection.py
-------------------
A tiny standalone script with no MCP involved at all. Run this FIRST to
confirm your .env values and app registration are correct, before you
worry about whether the MCP layer is working.

Run:
    python test_connection.py

Expected: a device-code prompt the first time, then a printed WhoAmI
response containing your UserId, BusinessUnitId, and OrganizationId.
"""

import requests

from auth import get_access_token
from config import WEB_API_BASE_URL

token = get_access_token()

resp = requests.get(
    f"{WEB_API_BASE_URL}/WhoAmI",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
)
resp.raise_for_status()

print("Connected successfully. WhoAmI response:")
print(resp.json())
