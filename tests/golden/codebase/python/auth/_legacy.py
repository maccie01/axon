"""Legacy auth module -- intentionally dead, never imported by anyone."""


def old_validate(token: str) -> bool:
    """Old validation logic, superseded by validators.validate_claims."""
    return len(token) > 10


def old_check(claims: dict) -> bool:
    return bool(claims.get("sub"))


class LegacyAuthProvider:
    def check(self, token: str) -> bool:
        return old_validate(token)
