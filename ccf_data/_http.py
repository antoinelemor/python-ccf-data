"""Low-level HTTP transport: a Session wrapper that handles auth, error
mapping, and surfacing tier/quota headers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests

from .exceptions import (
    CCFAuthError, CCFBadRequest, CCFError, CCFNotFound, CCFQuotaError,
    CCFServerError, CCFTierError,
)


DEFAULT_BASE_URL = "https://data.ccf-project.ca"
DEFAULT_TIMEOUT = 60  # seconds — server-side queries can be slow on 9.2M rows
DEFAULT_USER_AGENT = "ccf-data-python/0.1.0"


@dataclass
class TierStatus:
    """Tier + remaining quota, as surfaced by X-CCF-* response headers."""
    tier: Optional[str] = None
    requests_remaining: Optional[int] = None  # None when unlimited
    searches_remaining: Optional[int] = None
    exports_remaining: Optional[int] = None

    @classmethod
    def from_headers(cls, headers) -> "TierStatus":
        def _parse(name):
            v = headers.get(name)
            if v is None or v == 'unlimited':
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        return cls(
            tier=headers.get('X-CCF-Tier'),
            requests_remaining=_parse('X-CCF-Requests-Remaining'),
            searches_remaining=_parse('X-CCF-Searches-Remaining'),
            exports_remaining=_parse('X-CCF-Exports-Remaining'),
        )


class _HTTP:
    """Authenticated HTTP session for the CCF API.

    Tracks the most recent TierStatus so callers can introspect remaining
    quota after any request.
    """

    def __init__(self, token: str, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = DEFAULT_TIMEOUT,
                 user_agent: str = DEFAULT_USER_AGENT,
                 session: Optional[requests.Session] = None):
        if not token:
            raise CCFError("An API token is required. Generate one in the CCF "
                           "Data Explorer profile page (https://data.ccf-project.ca).")
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {token}',
            'User-Agent': user_agent,
            'Accept': 'application/json',
        })
        self.last_status: TierStatus = TierStatus()

    # ------------------------------------------------------------------
    def _url(self, path: str) -> str:
        if path.startswith('http://') or path.startswith('https://'):
            return path
        if not path.startswith('/'):
            path = '/' + path
        return self.base_url + path

    def _handle(self, response: requests.Response) -> Any:
        """Parse response, raising the right exception class on errors and
        capturing tier/quota info into self.last_status."""
        self.last_status = TierStatus.from_headers(response.headers)

        # Non-JSON success path (e.g. CSV export) — caller deals with content.
        if response.ok:
            ctype = (response.headers.get('Content-Type') or '').lower()
            if 'json' in ctype:
                return response.json()
            return response  # let the caller read .content / .text

        # Error path: parse JSON if possible
        try:
            data = response.json()
        except ValueError:
            data = {'error': response.text or response.reason}

        msg = data.get('error') or response.reason
        status = response.status_code

        if status == 401:
            raise CCFAuthError(f"401 Unauthorized: {msg}")
        if status == 403:
            if data.get('error') == 'tier_insufficient':
                raise CCFTierError(
                    data.get('message') or msg,
                    tier=data.get('tier'),
                    required_tier=data.get('required_tier'),
                )
            raise CCFAuthError(f"403 Forbidden: {msg}")
        if status == 404:
            raise CCFNotFound(f"404 Not Found: {msg}")
        if status == 429:
            raise CCFQuotaError(
                f"429 Quota exceeded: {data.get('reason') or msg}",
                reason=data.get('reason'),
                tier=data.get('tier'),
            )
        if status == 400:
            raise CCFBadRequest(f"400 Bad Request: {msg}")
        if 500 <= status < 600:
            raise CCFServerError(f"{status} Server Error: {msg}")
        raise CCFError(f"{status} {msg}")

    # ------------------------------------------------------------------
    def get(self, path: str, params=None, **kwargs):
        r = self._session.get(self._url(path), params=params,
                              timeout=self.timeout, **kwargs)
        return self._handle(r)

    def post(self, path: str, json=None, **kwargs):
        r = self._session.post(self._url(path), json=json,
                               timeout=self.timeout, **kwargs)
        return self._handle(r)

    def get_raw(self, path: str, params=None, **kwargs) -> requests.Response:
        """GET that always returns the raw Response (no JSON parsing).
        Used for binary endpoints like /api/search/export."""
        r = self._session.get(self._url(path), params=params,
                              timeout=self.timeout, **kwargs)
        if not r.ok:
            return self._handle(r)  # raises
        self.last_status = TierStatus.from_headers(r.headers)
        return r

    def post_raw(self, path: str, json=None, **kwargs) -> requests.Response:
        r = self._session.post(self._url(path), json=json,
                               timeout=self.timeout, **kwargs)
        if not r.ok:
            return self._handle(r)
        self.last_status = TierStatus.from_headers(r.headers)
        return r
