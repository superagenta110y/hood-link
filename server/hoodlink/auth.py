from fastapi import Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

from hoodlink.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    header_key: str | None = Security(_api_key_header),
) -> str:
    if header_key and header_key == settings.api_key:
        return header_key
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def require_api_key_ws(
    api_key: str | None = Query(None, alias="api_key"),
) -> str:
    if api_key and api_key == settings.api_key:
        return api_key
    raise HTTPException(status_code=401, detail="Invalid or missing API key")
