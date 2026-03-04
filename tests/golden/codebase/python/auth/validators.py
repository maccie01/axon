"""Auth validators -- edge cases: dataclass, TYPE_CHECKING, same-name validate()."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class TokenClaims:
    subject: str
    expiry: int
    scopes: list[str]


def validate_claims(token: str) -> TokenClaims | None:
    """Parse and validate token structure. Returns None if invalid."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    return TokenClaims(subject=parts[0], expiry=int(parts[1] or "0"), scopes=[])


def check_expiry(claims: TokenClaims) -> bool:
    """Check if claims have not expired."""
    import time
    return claims.expiry > int(time.time())


def validate(token: str) -> bool:
    """Same name as payments.gateway.validate -- edge case for call resolution."""
    claims = validate_claims(token)
    return claims is not None


def _unused_validator() -> None:
    """Dead code -- never called from anywhere."""
    pass
