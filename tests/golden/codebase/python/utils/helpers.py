"""Shared utilities -- edge case: wildcard import target, __all__ list."""
from __future__ import annotations

__all__ = ["format_amount", "truncate", "sanitize_input"]


def format_amount(amount: float, currency: str = "EUR") -> str:
    return f"{amount:.2f} {currency}"


def truncate(text: str, max_len: int = 100) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def sanitize_input(value: str) -> str:
    return value.strip().lower()


def validate(value: str) -> bool:
    """Third validate() -- must not be confused with auth.validators.validate
    or payments.gateway.validate."""
    return bool(value and value.strip())


def _private_util() -> None:
    """Not in __all__ but technically not dead if imported directly."""
    pass


def _truly_dead() -> None:
    """Not in __all__, never imported or called -- dead code."""
    pass
