"""Payment processor -- calls auth.service.validate_token (cross-file edge case)."""
from __future__ import annotations

from auth.service import validate_token, AuthService
from auth.validators import validate_claims
from payments.gateway import send_to_gateway, validate


class PaymentProcessor:
    """Inherits nothing -- standalone class using composition."""

    def __init__(self, auth: AuthService) -> None:
        self._auth = auth

    def process(self, token: str, amount: float) -> dict:
        if not self._auth.authenticate(token):
            return {"error": "unauthorized"}
        return charge_card(token, amount)

    def refund(self, token: str, transaction_id: str) -> bool:
        claims = validate_claims(token)
        if claims is None:
            return False
        return validate(token)


def charge_card(token: str, amount: float) -> dict:
    """Main entry point -- calls validate_token from auth.service (NOT auth.validators.validate)."""
    if not validate_token(token, "secret"):
        return {"error": "invalid token"}
    return send_to_gateway(amount)


def _internal_retry(amount: float, attempts: int = 3) -> bool:
    """Nested helper only called by charge_card indirectly -- via closure."""
    def attempt() -> bool:
        return amount > 0
    return attempt()
