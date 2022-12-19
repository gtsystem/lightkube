import sys
import typing
from typing import get_type_hints
from datetime import datetime
import dataclasses as dc

fromisoformat = datetime.fromisoformat


from .typing_extra import get_args, get_origin


def to_datetime(string):
    return fromisoformat(string.replace("Z", "+00:00"))


def from_datetime(dt):
    return dt.isoformat().replace("+00:00", "Z")


class ConverterFunc(typing.NamedTuple):
    from_json_type: typing.Callable
    to_json_type: typing.Callable


TYPE_CONVERTERS = {
    datetime: ConverterFunc(from_json_type=to_datetime, to_json_type=from_datetime)
}

EMPTY_DICT = {}


class Converter(typing.NamedTuple):
    is_list: bool
    supp_kw: bool
    func: typing.Callable

    def __call__(self, value, kw):
        if not self.supp_kw:
            kw = EMPTY_DICT
        if self.is_list:
            f = self.func
            return [f(_, **kw) for _ in value]
        return self.func(value, **kw)


def nohop(x, kw):
    return x


def is_dataclass_json(cls):
    return dc.is_dataclass(cls) and issubclass(cls, DataclassDictMixIn)


def extract_types(cls, is_to=True):
    func_name = "to_json_type" if is_to else "from_json_type"
    method_name = "to_dict" if is_to else "from_dict"
    types = get_type_hints(cls)
    for field in dc.fields(cls):
        k = field.name
        t = types[k]

        if get_origin(t) is list:
            is_list = True
            t = get_args(t)[0]
        else:
            is_list = False

        if is_dataclass_json(t):
            yield k, Converter(is_list=is_list, supp_kw=True, func=getattr(t, method_name)), field.default
        elif t in TYPE_CONVERTERS:
            yield k, Converter(is_list=is_list, supp_kw=False, func=getattr(TYPE_CONVERTERS[t], func_name)), field.default
        else:
            if is_to:
                yield k, nohop, field.default


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
    _late_init_from: typing.List = None
    _late_init_to: typing.List = None
    _json_to_prop: typing.Dict = None
    _prop_to_json: typing.Dict = None
    _valid_params: typing.Set = None

    @classmethod
    def _setup(cls):
        if cls._late_init_from is None:
            cls._late_init_from = list(t[:2] for t in extract_types(cls, is_to=False))
            for k, convert in cls._late_init_from:
                setattr(cls, k, LazyAttribute(k, convert))
            cls._prop_to_json = {field.name: field.metadata['json'] for field in dc.fields(cls) if 'json' in field.metadata}
            cls._json_to_prop = {v: k for k, v in cls._prop_to_json.items()}
            cls._late_init_to = list(extract_types(cls, is_to=True))
            cls._valid_params = {f.name for f in dc.fields(cls)}

    @classmethod
    def from_dict(cls, d, lazy=True):
        cls._setup()
        kwargs = dict(lazy=lazy)
        params = cls._valid_params
        valid_d = {}
        transform = cls._json_to_prop.get
        for k, v in d.items():
            k = transform(k, k)
            if k in params:
                valid_d[k] = v
        obj = cls(**valid_d)
        if lazy:
            obj._lazy_values = {}
            obj._lazy_kwargs = kwargs
            for k, _ in cls._late_init_from:
                obj._lazy_values[k] = getattr(obj, k)
                delattr(obj, k)
        else:
            d = obj.__dict__
            for k, convert in cls._late_init_from:
                if d[k] is not None:
                    d[k] = convert(d[k], kwargs)
        return obj

    def to_dict(self, dict_factory=dict):
        self._setup()
        kwargs = dict(dict_factory=dict_factory)
        result = []
        lazy_attr = getattr(self, "_lazy_values", None)
        key_transform = self._prop_to_json.get
        for k, conv_f, default in self._late_init_to:
            if lazy_attr is not None and k in lazy_attr:
                value = lazy_attr[k]
            else:
                value = getattr(self, k)
                if value == default:
                    continue
                value = conv_f(value, kwargs)
            if value is not None:
                result.append((key_transform(k, k), value))
        return dict_factory(result)
