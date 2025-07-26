from __future__ import annotations

from app.config import settings
from app.dependencies.database import get_redis
from app.fetcher import Fetcher

fetcher: Fetcher | None = None


def get_fetcher() -> Fetcher:
    global fetcher
    if fetcher is None:
        fetcher = Fetcher(
            settings.FETCHER_CLIENT_ID,
            settings.FETCHER_CLIENT_SECRET,
            settings.FETCHER_SCOPES,
            settings.FETCHER_CALLBACK_URL,
        )
        redis = get_redis()
        if redis:
            access_token = redis.get(f"fetcher:access_token:{fetcher.client_id}")
            if access_token:
                fetcher.access_token = str(access_token)
            refresh_token = redis.get(f"fetcher:refresh_token:{fetcher.client_id}")
            if refresh_token:
                fetcher.refresh_token = str(refresh_token)
            if not fetcher.access_token or not fetcher.refresh_token:
                print("Login to initialize fetcher:", fetcher.authorize_url)
    return fetcher
