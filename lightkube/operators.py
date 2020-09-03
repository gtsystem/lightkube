from typing import Iterable

__all__ = ['in_', 'not_in', 'exists', 'not_exists', 'equal', 'not_equal']


class Operator:
    def __init__(self, op: str, value):
        self.op = op
        self.value = value

    def encode(self, key):
        return f"{key}{self.op}{self.value}"


class SequenceOperator(Operator):
    def encode(self, key):
        return f"{key} {self.op} ({','.join(self.value)})"


class BinaryOperator(Operator):
    pass


class UnaryOperator(Operator):
    def encode(self, key):
        return f"{self.op}{key}"


def in_(values: Iterable) -> SequenceOperator:
    return SequenceOperator('in', sorted(values))


def not_in(values: Iterable) -> SequenceOperator:
    return SequenceOperator('notin', sorted(values))


def exists() -> UnaryOperator:
    return UnaryOperator('', None)


def not_exists() -> UnaryOperator:
    return UnaryOperator('!', None)


def equal(value: str) -> BinaryOperator:
    return BinaryOperator('=', value)


def not_equal(value: str) -> BinaryOperator:
    return BinaryOperator('!=', value)
