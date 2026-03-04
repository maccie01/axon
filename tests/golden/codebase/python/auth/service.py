"""Auth service -- edge cases: Protocol conformance, classmethod, async, super()."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .validators import TokenClaims

from .validators import check_expiry, validate_claims


@runtime_checkable
class Authenticator(Protocol):
    def authenticate(self, token: str) -> bool: ...


class BaseAuth:
    def authenticate(self, token: str) -> bool:
        return False

    def _log(self, message: str) -> None:
        pass


class AuthService(BaseAuth):
    """Main auth service -- calls validators, uses super()."""

    def __init__(self, secret: str) -> None:
        super().__init__()
        self.secret = secret
        self._cache: dict[str, bool] = {}

    def authenticate(self, token: str) -> bool:
        if token in self._cache:
            return self._cache[token]
        result = validate_token(token, self.secret)
        self._cache[token] = result
        return result

    @classmethod
    def from_env(cls) -> "AuthService":
        import os
        secret = os.environ.get("AUTH_SECRET", "default")
        return cls(secret)

    @staticmethod
    def hash_token(token: str) -> str:
        return token[::-1]

    @property
    def is_configured(self) -> bool:
        return bool(self.secret)

    async def async_authenticate(self, token: str) -> bool:
        return self.authenticate(token)


def validate_token(token: str, secret: str) -> bool:
    """Top-level function -- same name exists in payments.gateway (edge case)."""
    if not token:
        return False
    claims = validate_claims(token)
    if claims is None:
        return False
    return check_expiry(claims)


def init() -> None:
    """Called from main.py startup."""
    pass


def _internal_helper() -> str:
    """Only called within this module."""
    return "internal"


def _dead_in_service() -> None:
    """Never called -- dead code within a live module."""
    _internal_helper()
