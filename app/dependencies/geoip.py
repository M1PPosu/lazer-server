# -*- coding: utf-8 -*-
"""
GeoIP dependency for FastAPI
"""
from functools import lru_cache
from app.helpers.geoip_helper import GeoIPHelper
from app.config import settings

@lru_cache()
def get_geoip_helper() -> GeoIPHelper:
    """
    获取 GeoIP 帮助类实例
    使用 lru_cache 确保单例模式
    """
    return GeoIPHelper(
        dest_dir=settings.geoip_dest_dir,
        license_key=settings.maxmind_license_key,
        editions=["City", "ASN"],
        max_age_days=8,
        timeout=60.0
    )


def get_client_ip(request) -> str:
    """
    Get the real client IP address
    Supports proxies, load balancers, and Cloudflare headers
    """
    headers = request.headers

    # 1. Cloudflare specific headers
    cf_ip = headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    true_client_ip = headers.get("True-Client-IP")
    if true_client_ip:
        return true_client_ip.strip()

    # 2. Standard proxy headers
    forwarded_for = headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may contain multiple IPs, take the first
        return forwarded_for.split(",")[0].strip()

    real_ip = headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 3. Fallback to client host
    return request.client.host if request.client else "127.0.0.1"
