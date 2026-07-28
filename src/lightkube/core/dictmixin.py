"""
DictMixin — msgspec.Struct-based base class for lightkube model objects.

Provides from_dict / to_dict compatibility methods.
"""

import warnings

import msgspec

__all__ = ["DictMixin", "field"]

# Re-export so model files can import field from one place
field = msgspec.field

to_builtins = msgspec.to_builtins


def _to_factory(dict_factory, obj):
    """Recursively convert a msgspec Struct (or nested structures) to dict_factory instances."""
    if isinstance(obj, msgspec.Struct):
        return dict_factory(
            (k, _to_factory(dict_factory, v)) for k, v in msgspec.structs.asdict(obj).items() if v is not msgspec.NODEFAULT
        )
    elif isinstance(obj, list):
        return [_to_factory(dict_factory, item) for item in obj]
    elif isinstance(obj, dict):
        return dict_factory((k, _to_factory(dict_factory, v)) for k, v in obj.items())
    return obj


class DictMixin(msgspec.Struct, omit_defaults=True):
    """Base class for lightkube model objects backed by msgspec.Struct."""

    @classmethod
    def from_dict(cls, d: dict, lazy: bool = False) -> "DictMixin":
        """Construct an instance from a plain dict (e.g. parsed from YAML or JSON).

        The ``lazy`` parameter is ignored — msgspec decodes eagerly and is fast enough
        that deferred conversion is unnecessary. Passing ``lazy=True`` emits a deprecation
        warning; passing ``lazy=False`` is silently accepted (it was already the effective
        behaviour).
        """
        if lazy:
            warnings.warn(
                "lazy=True is deprecated and has no effect; "
                "msgspec.Struct decodes eagerly. Pass lazy=False to suppress this warning.",
                DeprecationWarning,
                stacklevel=2,
            )
        return msgspec.convert(d, cls)

    def to_dict(self, dict_factory=dict) -> dict:
        """Serialise to a plain dict, omitting fields that equal their default value.

        The optional ``dict_factory`` parameter is deprecated. It was supported by the
        old ``DataclassDictMixIn`` implementation; passing anything other than the default
        ``dict`` now emits a deprecation warning. Use plain ``dict`` (the default) instead.
        """
        if dict_factory is not dict:
            warnings.warn(
                "dict_factory is deprecated and will be removed in a future release. Use the default dict instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return _to_factory(dict_factory, to_builtins(self))
        return to_builtins(self)
