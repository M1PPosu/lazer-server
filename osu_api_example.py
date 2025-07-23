from __future__ import annotations

import os

import requests

CLIENT_ID = os.environ.get("OSU_CLIENT_ID", "5")
CLIENT_SECRET = os.environ.get(
    "OSU_CLIENT_SECRET", "FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk"
)
API_URL = os.environ.get("OSU_API_URL", "https://osu.ppy.sh")


def authenticate(username: str, password: str):
    """Authenticate via OAuth password flow and return the token dict."""
    url = f"{API_URL}/oauth/token"
    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "*",
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()


def refresh_token(refresh: str):
    """Refresh the OAuth token."""
    url = f"{API_URL}/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "*",
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()


def get_current_user(access_token: str, ruleset: str = "osu"):
    """Retrieve the authenticated user's data."""
    url = f"{API_URL}/api/v2/me/{ruleset}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    import getpass

    username = input("osu! username: ")
    password = getpass.getpass()

    token = authenticate(username, password)
    print("Access Token:", token["access_token"])
    user = get_current_user(token["access_token"])

    print(user)
