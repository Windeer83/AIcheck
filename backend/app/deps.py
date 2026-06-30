from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


def require_access_token(
    authorization: str | None = Header(default=None),
    x_access_token: str | None = Header(default=None, alias="X-Access-Token"),
) -> None:
    expected = settings.app_access_token
    provided = x_access_token
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()
    if expected and provided != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

