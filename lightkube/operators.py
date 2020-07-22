from typing import Iterable

__all__ = ['in_', 'not_in', 'exist', 'not_exist', 'equal', 'not_equal']


class Operator:
    def __init__(self, op: str, value):
        self.op = op
        self.value = value

    def encode(self, key):
        return f"{key}{self.op}{self.value}"


class SequenceOperator(Operator):
    def encode(self, key):
        return f"{key} {self.op} ({','.join(self.value)})"


class UnaryOperator(Operator):
    def encode(self, key):
        return f"{self.op}{key}"


def in_(values: Iterable):
    return SequenceOperator('in', sorted(values))


def not_in(values: Iterable):
    return SequenceOperator('notin', sorted(values))


def exist():
    return UnaryOperator('', None)


def not_exist():
    return UnaryOperator('!', None)


def equal(value: str):
    return Operator('=', value)


def not_equal(value: str):
    return Operator('!=', value)

