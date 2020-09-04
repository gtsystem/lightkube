from typing import Iterable

__all__ = ['in_', 'not_in', 'exists', 'not_exists', 'equal', 'not_equal']


class Operator:
    def __init__(self, op_name: str, op: str, value=None):
        self.op = op
        self.value = value
        self.op_name = op_name

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
    return SequenceOperator('in_', 'in', sorted(values))


def not_in(values: Iterable) -> SequenceOperator:
    return SequenceOperator('not_in', 'notin', sorted(values))


def exists() -> UnaryOperator:
    return UnaryOperator('exists', '')


def not_exists() -> UnaryOperator:
    return UnaryOperator('not_exists', '!')


def equal(value: str) -> BinaryOperator:
    return BinaryOperator('equal', '=', value)


def not_equal(value: str) -> BinaryOperator:
    return BinaryOperator('not_equal', '!=', value)

