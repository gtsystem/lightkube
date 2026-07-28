"""
Decode helpers and lazy-cached structs for Kubernetes API responses.

List models are created on first use with msgspec.defstruct so they can be
decoded directly from bytes without an intermediate Python dict.

The Watch struct is a single reusable class: the ``object`` field is always
``msgspec.Raw`` regardless of the resource type, so there is no per-resource
variant and no caching needed.
"""

from typing import Any, Callable, List, Optional, Tuple, Type

import msgspec

from .internal_models import meta_v1

__all__ = ["decode_list", "decode_object", "decode_status", "decode_watch_event"]

# Local alias avoids repeated attribute lookups on the hot decode path.
json_decode = msgspec.json.decode

_list_models: dict = {}


def _identity(x):
    return x


class ListMetadata(msgspec.Struct, omit_defaults=True):
    resourceVersion: Optional[str] = None
    continue_: Optional[str] = msgspec.field(name="continue", default=None)


class WatchEvent(msgspec.Struct, omit_defaults=True):
    """Single event returned by the Kubernetes watch stream.

    ``object`` is left as ``msgspec.Raw`` so the caller can inspect ``type``
    first and then decode ``object`` into the correct type (resource or Status)
    without a ``ValidationError``.
    """

    type: str
    object: msgspec.Raw


def _is_struct(res: Type) -> bool:
    return isinstance(res, type) and issubclass(res, msgspec.Struct)


def _get_list_model(res: Type) -> Tuple[type, Callable]:
    cached = _list_models.get(res)
    if cached is not None:
        return cached

    if _is_struct(res):
        item_type: Any = res
        mapper = _identity
    else:
        item_type = Any
        mapper = res

    fields: list = [
        ("items", List[item_type]),
        ("metadata", Optional[ListMetadata], msgspec.field(default=None)),  # type: ignore[misc]
    ]
    model = msgspec.defstruct(
        f"{res.__name__}List",
        fields,
        omit_defaults=True,
    )
    result = (model, mapper)
    _list_models[res] = result
    return result


def decode_watch_event(line: bytes) -> WatchEvent:
    """Decode a raw watch-stream line into a ``WatchEvent``."""
    return json_decode(line, type=WatchEvent)


def decode_status(data: bytes) -> "meta_v1.Status":
    """Decode *data* as a Kubernetes ``Status`` object."""
    return json_decode(data, type=meta_v1.Status)


def decode_object(data: bytes, res: Type):
    """Decode *data* into an instance of *res*.

    - ``msgspec.Struct`` subclasses: decoded directly via ``msgspec.json.decode``.
    - ``dict`` subclasses: decoded as ``Any`` (plain ``dict``) then wrapped by
      calling ``res(decoded)``.
    """
    if _is_struct(res):
        return json_decode(data, type=res)
    return res(json_decode(data, type=Any))


def decode_list(data: bytes, res: Type) -> Tuple[Optional[str], Optional[str], list]:
    """Decode a Kubernetes list response body for the given resource class.

    Returns ``(continue_token, resource_version, items)`` where:
    - ``continue_token`` is the server-supplied pagination token, or ``None`` when
      there are no more pages.
    - ``resource_version`` is the list metadata ``resourceVersion``, or ``None``.
    - ``items`` is the decoded list of resource instances.
    """
    model, mapper = _get_list_model(res)
    decoded: Any = json_decode(data, type=model)
    cont = decoded.metadata.continue_ if decoded.metadata else None
    try:
        rv = decoded.metadata.resourceVersion if decoded.metadata else None
    except AttributeError:
        rv = None
    return cont, rv, [mapper(item) for item in decoded.items]
