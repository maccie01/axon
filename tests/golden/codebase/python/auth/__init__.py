"""Auth package -- re-exports public API via __init__.py (edge case: re-exports)."""
from .service import AuthService, validate_token
from .validators import check_expiry, validate_claims

__all__ = ["AuthService", "validate_token", "check_expiry", "validate_claims"]
