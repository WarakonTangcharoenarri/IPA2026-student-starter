"""Part 4 student implementation."""

import os
from urllib.parse import quote

import requests


WEBEX_API_BASE = "https://webexapis.com/v1"
_REQUEST_TIMEOUT = 10


class WebexClient:
    def __init__(self, token=None, session=None):
        self._token = token or os.environ.get("WEBEX_BOT_TOKEN")
        if not self._token:
            raise PermissionError("WEBEX_BOT_TOKEN is not configured")
        self._session = session or requests.Session()

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_message(self, message_id):
        response = self._session.get(
            f"{WEBEX_API_BASE}/messages/{quote(message_id, safe='')}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def download_file(self, file_url):
        response = self._session.get(
            file_url,
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.content

    def send_message(self, room_id, text):
        response = self._session.post(
            f"{WEBEX_API_BASE}/messages",
            headers=self.headers,
            json={"roomId": room_id, "text": text},
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def get_me(self):
        response = self._session.get(
            f"{WEBEX_API_BASE}/people/me",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
