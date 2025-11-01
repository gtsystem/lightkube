import pytest

from lightkube import operators
from lightkube.core.selector import build_selector


def test_simple_types():
    r = build_selector({"k1": "v1", "k2": None, "k3": ["b", "c"], "k4": {"a", "b"}, "k5": ("d", "b")})

    assert r == "k1=v1,k2,k3 in (b,c),k4 in (a,b),k5 in (b,d)"


def test_operators():
    r = build_selector(
        {
            "k1": operators.equal("v1"),
            "k2": operators.not_exists(),
            "k3": operators.in_(["b", "c"]),
            "k4": operators.not_in(["b", "c"]),
            "k5": operators.not_equal("v5"),
            "k6": operators.exists(),
        }
    )

    assert r == "k1=v1,!k2,k3 in (b,c),k4 notin (b,c),k5!=v5,k6"


def test_binary_only_selector():
    with pytest.raises(ValueError):
        build_selector({"k2": None}, for_fields=True)

    with pytest.raises(ValueError):
        build_selector({"k2": operators.in_(["b", "c"])}, for_fields=True)

    r = build_selector({"k1": "a", "k2": operators.not_equal("a")}, for_fields=True)
    assert r == "k1=a,k2!=a"

    r = build_selector({"k1": "a", "k2": operators.not_in(["a", "b"])}, for_fields=True)
    assert r == "k1=a,k2!=a,k2!=b"
