from __future__ import annotations

import secrets

from app.database.auth import OAuthClient, OAuthToken
from app.dependencies.database import get_db, get_redis

from .router import router

from fastapi import Body, Depends, HTTPException
from redis.asyncio import Redis
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession


@router.post("/oauth-app/create", tags=["OAuth"])
async def create_oauth_app(
    name: str = Body(..., max_length=100),
    description: str = Body(""),
    redirect_uris: list[str] = Body(...),
    owner_id: int = Body(...),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(  # pyright: ignore[reportDeprecated]
        text(
            "SELECT AUTO_INCREMENT FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'oauth_clients'"
        )
    )
    next_id = result.one()[0]
    if next_id < 10:
        await session.execute(text("ALTER TABLE oauth_clients AUTO_INCREMENT = 10"))
        await session.commit()

    oauth_client = OAuthClient(
        name=name,
        description=description,
        redirect_uris=redirect_uris,
        owner_id=owner_id,
    )
    session.add(oauth_client)
    await session.commit()
    await session.refresh(oauth_client)
    return {
        "client_id": oauth_client.client_id,
        "client_secret": oauth_client.client_secret,
        "redirect_uris": oauth_client.redirect_uris,
    }


@router.get("/oauth-apps/{client_id}", tags=["OAuth"])
async def get_oauth_app(client_id: int, session: AsyncSession = Depends(get_db)):
    oauth_app = await session.get(OAuthClient, client_id)
    if not oauth_app:
        raise HTTPException(status_code=404, detail="OAuth app not found")
    return {
        "name": oauth_app.name,
        "description": oauth_app.description,
        "redirect_uris": oauth_app.redirect_uris,
        "client_id": oauth_app.client_id,
    }


@router.get("/oauth-apps/user/{owner_id}", tags=["OAuth"])
async def get_user_oauth_apps(owner_id: int, session: AsyncSession = Depends(get_db)):
    oauth_apps = await session.exec(
        select(OAuthClient).where(OAuthClient.owner_id == owner_id)
    )
    return [
        {
            "name": app.name,
            "description": app.description,
            "redirect_uris": app.redirect_uris,
            "client_id": app.client_id,
        }
        for app in oauth_apps
    ]


@router.delete("/oauth-app/{client_id}", tags=["OAuth"], status_code=204)
async def delete_oauth_app(
    client_id: int,
    session: AsyncSession = Depends(get_db),
):
    oauth_client = await session.get(OAuthClient, client_id)
    if not oauth_client:
        raise HTTPException(status_code=404, detail="OAuth app not found")

    tokens = await session.exec(
        select(OAuthToken).where(OAuthToken.client_id == client_id)
    )
    for token in tokens:
        await session.delete(token)

    await session.delete(oauth_client)
    await session.commit()


@router.patch("/oauth-app/{client_id}", tags=["OAuth"])
async def update_oauth_app(
    client_id: int,
    name: str = Body(..., max_length=100),
    description: str = Body(""),
    redirect_uris: list[str] = Body(...),
    session: AsyncSession = Depends(get_db),
):
    oauth_client = await session.get(OAuthClient, client_id)
    if not oauth_client:
        raise HTTPException(status_code=404, detail="OAuth app not found")

    oauth_client.name = name
    oauth_client.description = description
    oauth_client.redirect_uris = redirect_uris

    await session.commit()
    await session.refresh(oauth_client)

    return {
        "client_id": oauth_client.client_id,
        "client_secret": oauth_client.client_secret,
        "redirect_uris": oauth_client.redirect_uris,
    }


@router.post("/oauth-app/{client_id}/refresh", tags=["OAuth"])
async def refresh_secret(
    client_id: int,
    session: AsyncSession = Depends(get_db),
):
    oauth_client = await session.get(OAuthClient, client_id)
    if not oauth_client:
        raise HTTPException(status_code=404, detail="OAuth app not found")

    oauth_client.client_secret = secrets.token_hex()
    tokens = await session.exec(
        select(OAuthToken).where(OAuthToken.client_id == client_id)
    )
    for token in tokens:
        await session.delete(token)

    await session.commit()
    await session.refresh(oauth_client)

    return {
        "client_id": oauth_client.client_id,
        "client_secret": oauth_client.client_secret,
        "redirect_uris": oauth_client.redirect_uris,
    }


@router.post("/oauth-app/{client_id}/code")
async def generate_oauth_code(
    client_id: int,
    user_id: int = Body(...),
    redirect_uri: str = Body(...),
    scopes: list[str] = Body(...),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    client = await session.get(OAuthClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="OAuth app not found")

    if redirect_uri not in client.redirect_uris:
        raise HTTPException(
            status_code=403, detail="Redirect URI not allowed for this client"
        )

    code = secrets.token_urlsafe(80)
    await redis.hset(  # pyright: ignore[reportGeneralTypeIssues]
        f"oauth:code:{client_id}:{code}",
        mapping={"user_id": user_id, "scopes": ",".join(scopes)},
    )
    await redis.expire(f"oauth:code:{client_id}:{code}", 300)
