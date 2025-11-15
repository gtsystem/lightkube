from typing import Generic, Iterable, TypeVar

__all__ = ["equal", "exists", "in_", "not_equal", "not_exists", "not_in"]

T_Y = TypeVar("T_Y")


class Operator(Generic[T_Y]):
    def __init__(self, op_name: str, op: str, value: T_Y) -> None:
        self.op = op
        self.value: T_Y = value
        self.op_name = op_name

    def encode(self, key: str) -> str:
        return f"{key}{self.op}{self.value}"


class SequenceOperator(Operator[Iterable[str]]):
    def encode(self, key: str) -> str:
        return f"{key} {self.op} ({','.join(self.value)})"


class BinaryOperator(Operator[str]):
    pass


class UnaryOperator(Operator[None]):
    def __init__(self, op_name: str, op: str) -> None:
        super().__init__(op_name, op, value=None)

    def encode(self, key: str) -> str:
        return f"{self.op}{key}"


def in_(values: Iterable[str]) -> SequenceOperator:
    return SequenceOperator("in_", "in", sorted(values))


def not_in(values: Iterable[str]) -> SequenceOperator:
    return SequenceOperator("not_in", "notin", sorted(values))


def exists() -> UnaryOperator:
    return UnaryOperator("exists", "")


def not_exists() -> UnaryOperator:
    return UnaryOperator("not_exists", "!")


def equal(value: str) -> BinaryOperator:
    return BinaryOperator("equal", "=", value)


def not_equal(value: str) -> BinaryOperator:
    return BinaryOperator("not_equal", "!=", value)
