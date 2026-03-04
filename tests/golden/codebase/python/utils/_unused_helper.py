"""Dead module -- never imported by anything in the codebase."""


def dead_function_one() -> str:
    return "never called"


def dead_function_two(x: int) -> int:
    return x * 2


class DeadClass:
    def method(self) -> None:
        dead_function_one()
