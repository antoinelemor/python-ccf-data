"""Exceptions raised by ccf_data."""


class CCFError(Exception):
    """Base class for all ccf_data errors."""


class CCFAuthError(CCFError):
    """Raised when the API rejects the token (401)."""


class CCFTierError(CCFError):
    """Raised when the token's tier is too low for the requested endpoint (403)."""

    def __init__(self, message, tier=None, required_tier=None):
        super().__init__(message)
        self.tier = tier
        self.required_tier = required_tier


class CCFQuotaError(CCFError):
    """Raised when the token has exhausted its daily/total quota (429)."""

    def __init__(self, message, reason=None, tier=None):
        super().__init__(message)
        self.reason = reason
        self.tier = tier


class CCFNotFound(CCFError):
    """Raised on 404 responses."""


class CCFServerError(CCFError):
    """Raised on 5xx responses."""


class CCFBadRequest(CCFError):
    """Raised on 400 responses."""
