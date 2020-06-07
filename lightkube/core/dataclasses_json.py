from typing import Optional
from dataclasses import dataclass
import dataclasses as dc
from typing import get_type_hints
import typing
from functools import partial


def dataclass_json(_cls=None, *, letter_case=None):
    def wrap(cls):
        return _process_class(cls, letter_case)

    if _cls is None:
        return wrap
    return wrap(_cls)


def convert_item(from_dict, value, kwargs):
    return from_dict(value, **kwargs)


def convert_list(from_dict, value, kwargs):
    return [from_dict(_, **kwargs) for _ in value]


def extract_types(cls):
    types = {}
    for k, t in get_type_hints(cls).items():
        if dc.is_dataclass(t):
            types[k] = partial(convert_item, t.from_dict)
        elif typing.get_origin(t) is list and dc.is_dataclass(typing.get_args(t)[0]):
            types[k] = partial(convert_list, typing.get_args(t)[0].from_dict)
    return types


class LazyAttribute:
    def __init__(self, key, convert):
        self.key = key
        self.convert = convert

    def __get__(self, instance, owner):
        value = instance._lazy_values[self.key]
        if value is not None:
            value = self.convert(value, instance._lazy_kwargs)
        setattr(instance, self.key, value)
        del instance._lazy_values[self.key]
        return value


class DataclassDictMixIn:
    def __init__(self, **kwargs):
        pass

    @classmethod
    def from_dict(cls, d, lazy=True):
        kwargs = dict(lazy=lazy)
        if cls._late_init is None:
            cls._late_init = extract_types(cls)
            for k, convert in cls._late_init.items():
                setattr(cls, k, LazyAttribute(k, convert))

        if lazy:
            obj = cls(**d)
            obj._lazy_values = {}
            obj._lazy_kwargs = kwargs
            for k in cls._late_init:
                obj._lazy_values[k] = getattr(obj, k)
                delattr(obj, k)
        else:
            obj = cls(**d)
            d = obj.__dict__
            for k, convert in cls._late_init.items():
                d[k] = convert(d[k], kwargs)
        return obj


def _process_class(cls, letter_case):
    cls.from_dict = classmethod(DataclassDictMixIn.from_dict.__func__)
    cls._late_init = None
    return cls
