import os
from fastapi import HTTPException, Request


def verify_bearer_token(request: Request) -> None:
    expected_token = os.getenv("API_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(status_code=500, detail="API token is not configured")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    provided_token = auth_header.replace("Bearer ", "", 1).strip()
    if provided_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
