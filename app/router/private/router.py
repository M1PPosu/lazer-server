from __future__ import annotations

import hashlib
import hmac
import time

from app.config import settings

from fastapi import APIRouter, Depends, Header, HTTPException, Request


async def verify_signature(
    request: Request,
    ts: int = Header(..., alias="X-Timestamp"),
    nonce: str = Header(..., alias="X-Nonce"),
    signature: str = Header(..., alias="X-Signature"),
):
    path = request.url.path
    data = await request.body()
    body = data.decode("utf-8")

    py_ts = ts // 1000
    if abs(time.time() - py_ts) > 30:
        raise HTTPException(status_code=403, detail="Invalid timestamp")

    payload = f"{path}|{body}|{ts}|{nonce}"
    expected_sig = hmac.new(
        settings.private_api_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")


router = APIRouter(
    prefix="/api/private",
    dependencies=[Depends(verify_signature)],
    include_in_schema=settings.debug,
    tags=["私有 API"],
)
