"""Entry point -- edge cases: wildcard import, calls init() from auth.service."""
from utils.helpers import *  # noqa: F401,F403  -- wildcard import edge case
from auth.service import init, AuthService
from payments.processor import PaymentProcessor


def startup() -> None:
    """Application startup -- calls auth.service.init."""
    init()


def run(token: str, amount: float) -> dict:
    """Main flow: authenticate then process payment."""
    auth = AuthService.from_env()
    processor = PaymentProcessor(auth)
    return processor.process(token, amount)


if __name__ == "__main__":
    startup()
    result = run("test.1234567890.sig", 42.0)
    print(result)
