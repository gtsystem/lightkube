"""
This module exposes dependencies used by lightkube models.

`dataclass` is a no-op because msgspec.Struct handles class construction itself.
`field` translates the dataclasses metadata={"json": ...} convention to msgspec's name= kwarg.
"""

__all__ = ["DictMixin", "dataclass", "field"]

import msgspec

from .dictmixin import DictMixin


def dataclass(cls):
    """No-op decorator. msgspec.Struct subclasses do not need @dataclass."""
    return cls


def field(metadata=None, default=msgspec.NODEFAULT, default_factory=msgspec.NODEFAULT, **kwargs):
    """Compatibility wrapper around msgspec.field.

    Translates dataclasses-style metadata={"json": "name"} to msgspec's name= kwarg.
    default_factory is not supported by msgspec.Struct fields; use a plain default instead.
    """
    if metadata and "json" in metadata:
        kwargs["name"] = metadata["json"]
    if default is not msgspec.NODEFAULT:
        kwargs["default"] = default
    elif default_factory is not msgspec.NODEFAULT:
        # msgspec does not support default_factory; this would only be hit if a model
        # uses field(default_factory=...) which doesn't appear in the generated models.
        raise TypeError("default_factory is not supported for msgspec.Struct fields")
    return msgspec.field(**kwargs)
