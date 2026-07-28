"""Tests for the msgspec-backed DictMixin."""

from typing import List, Optional

import msgspec

from lightkube.core.dictmixin import DictMixin

# ---------------------------------------------------------------------------
# Simple model definitions used throughout the tests
# ---------------------------------------------------------------------------


class A(DictMixin):
    a1: str
    a2: int = 0
    a3: bool = False


class B(DictMixin):
    b1: str
    b2: Optional[A] = None
    b3: Optional[dict] = None


class C(DictMixin):
    c1: str
    c2: Optional[List[A]] = None
    c3: Optional[str] = msgspec.field(name="$ref", default=None)


class Def(DictMixin):
    d1: str
    d2: int = 2
    d3: bool = False
    d4: str = "ok"


# ---------------------------------------------------------------------------
# from_dict / to_dict
# ---------------------------------------------------------------------------


def test_single():
    a = A.from_dict({"a1": "a", "a3": True})
    assert a.a1 == "a"
    assert a.a2 == 0
    assert a.a3 is True
    assert a.to_dict() == {"a1": "a", "a3": True}


def test_nested():
    b = B.from_dict({"b1": "ok", "b2": {"a1": "a", "a3": True}})
    assert b.b1 == "ok"
    assert b.b2.a3 is True
    assert b.to_dict() == {"b1": "ok", "b2": {"a1": "a", "a3": True}}


def test_nested_in_list():
    c = C.from_dict({"c1": "ok", "c2": [{"a1": "a", "a3": True}, {"a1": "b"}]})
    assert c.c2[0].a3 is True
    assert c.c2[1].a1 == "b"
    assert c.to_dict() == {"c1": "ok", "c2": [{"a1": "a", "a3": True}, {"a1": "b"}]}


def test_dict_field():
    b = B.from_dict({"b1": "ok", "b3": {"xx": "x"}})
    assert b.to_dict() == {"b1": "ok", "b3": {"xx": "x"}}


def test_drop_unknown():
    """Unknown attributes are dropped during decode."""
    c = C.from_dict({"c1": "a", "k": "b"})
    assert c.c1 == "a"
    assert not hasattr(c, "k")
    assert c.to_dict() == {"c1": "a"}


def test_rename():
    """Fields with a JSON alias are round-tripped correctly."""
    c = C.from_dict({"c1": "a", "$ref": "b"})
    assert c.c1 == "a"
    assert c.c3 == "b"
    assert c.to_dict() == {"c1": "a", "$ref": "b"}


def test_default_not_encoded():
    """Default values are omitted from to_dict output."""
    assert Def(d1="a").to_dict() == {"d1": "a"}
    assert Def(d1="a", d2=2).to_dict() == {"d1": "a"}
    assert Def(d1="a", d2=0).to_dict() == {"d1": "a", "d2": 0}
    assert Def(d1="a", d3=False).to_dict() == {"d1": "a"}
    assert Def(d1="a", d3=True).to_dict() == {"d1": "a", "d3": True}
    assert Def(d1="a", d4="ok").to_dict() == {"d1": "a"}
    assert Def(d1="a", d4="ko").to_dict() == {"d1": "a", "d4": "ko"}


def test_nested_mutation():
    """Mutating a field after construction is reflected in to_dict."""
    c = C.from_dict({"c1": "val"})
    assert c.to_dict() == {"c1": "val"}
    c.c2 = [A(a1="def")]
    assert c.to_dict() == {"c1": "val", "c2": [{"a1": "def"}]}


def test_clear_optional_field():
    c = C.from_dict({"c1": "val", "c2": [{"a1": "abc"}]})
    assert c.to_dict() == {"c1": "val", "c2": [{"a1": "abc"}]}
    c.c2 = None
    assert c.to_dict() == {"c1": "val"}


# ---------------------------------------------------------------------------
# msgspec.json.encode / msgspec.json.decode (the direct path used by the client)
# ---------------------------------------------------------------------------


def test_to_json():
    a = A(a1="hi", a3=True)
    assert msgspec.json.encode(a) == b'{"a1":"hi","a3":true}'


def test_to_json_list():
    items = [A(a1="x"), A(a1="y", a2=1)]
    assert msgspec.json.encode(items) == b'[{"a1":"x"},{"a1":"y","a2":1}]'


def test_to_json_dict():
    assert msgspec.json.encode({"key": "val"}) == b'{"key":"val"}'


def test_from_json():
    buf = b'{"a1":"hi","a3":true}'
    a = msgspec.json.decode(buf, type=A)
    assert isinstance(a, A)
    assert a.a1 == "hi"
    assert a.a3 is True
    assert a.a2 == 0


def test_from_json_nested():
    buf = b'{"b1":"ok","b2":{"a1":"a","a3":true}}'
    b = msgspec.json.decode(buf, type=B)
    assert b.b2.a3 is True
    assert b.to_dict() == {"b1": "ok", "b2": {"a1": "a", "a3": True}}


def test_roundtrip_json():
    original = C(c1="hello", c2=[A(a1="x", a2=5)], c3="ref-val")
    buf = msgspec.json.encode(original)
    decoded = msgspec.json.decode(buf, type=C)
    assert decoded.c1 == original.c1
    assert decoded.c2[0].a2 == 5
    assert decoded.c3 == "ref-val"
