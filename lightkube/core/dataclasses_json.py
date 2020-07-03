from typing import Optional
from dataclasses import dataclass
import dataclasses as dc
from typing import get_type_hints
import typing
from functools import partial
import inspect
from datetime import datetime


def to_datetime(string, **_):
    return datetime.fromisoformat(string.replace("Z", "+00:00"))


TYPE_MAPPING = {
    datetime: to_datetime
}


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
        if typing.get_origin(t) is list:
            convert = convert_list
            t = typing.get_args(t)[0]
        else:
            convert = convert_item

        if dc.is_dataclass(t) and hasattr(t, 'from_dict'):
            types[k] = partial(convert, t.from_dict)
        elif t in TYPE_MAPPING:
            types[k] = partial(convert, TYPE_MAPPING[t])

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

        params = inspect.signature(cls).parameters
        d = {k: v for k, v in d.items() if k in params}
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
                if d[k] is not None:
                    d[k] = convert(d[k], kwargs)
        return obj


def _process_class(cls, letter_case):
    cls.from_dict = classmethod(DataclassDictMixIn.from_dict.__func__)
    cls._late_init = None
    return cls
