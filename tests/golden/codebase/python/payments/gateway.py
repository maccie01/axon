"""Payment gateway -- external API connector. Edge case: same-name validate()."""
from __future__ import annotations

import functools
from typing import Callable


def retry(max_attempts: int = 3) -> Callable:
    """Decorator factory -- edge case: decorator-wrapped function."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    pass
            return None
        return wrapper
    return decorator


@retry(max_attempts=3)
def send_to_gateway(amount: float) -> dict:
    """Calls external API. Decorated with @retry."""
    if amount <= 0:
        raise ValueError("Amount must be positive")
    return {"status": "ok", "amount": amount}


def validate(token: str) -> bool:
    """Same name as auth.validators.validate -- MUST NOT be confused with it."""
    return token.startswith("pay_")


def _unused_gateway_helper() -> None:
    """Dead code -- never called from outside this module or within it."""
    pass
