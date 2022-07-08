import decimal
import pytest

from lightkube.models.core_v1 import ResourceRequirements
from lightkube.utils.quantity import parse_quantity
from lightkube.utils.quantity import equals_canonically


def test_unitless():
    """Unitless values must be interpreted as decimal notation."""
    assert parse_quantity("1.5") == decimal.Decimal("1.5")
    assert parse_quantity("-1.5") == decimal.Decimal("-1.5")
    assert parse_quantity("0.30000000000000004") == decimal.Decimal("0.301")
    assert parse_quantity("0.09999999999999998") == decimal.Decimal("0.1")
    assert parse_quantity("3.141592653") == decimal.Decimal("3.142")


def test_binary_notation():
    assert parse_quantity("1.5Gi") == parse_quantity("1536Mi") == decimal.Decimal("1610612736")
    assert parse_quantity("0.9Gi") == decimal.Decimal("966367641.6")


def test_decimal_notation():
    assert parse_quantity("1.5G") == decimal.Decimal("1500000000")
    assert parse_quantity("0.9G") == decimal.Decimal("900000000")
    assert parse_quantity("500m") == decimal.Decimal("0.5")


def test_none():
    assert parse_quantity(None) is None


def test_invalid_value():
    with pytest.raises(ValueError):
        parse_quantity("1.2.3")
    with pytest.raises(ValueError):
        parse_quantity("1e2.3")
    with pytest.raises(ValueError):
        # decimal.InvalidOperation
        parse_quantity("9e999")
    with pytest.raises(ValueError):
        # decimal.Overflow
        parse_quantity("9e9999999")


def test_invalid_unit():
    with pytest.raises(ValueError):
        parse_quantity("1kb")
    with pytest.raises(ValueError):
        parse_quantity("1GGi")


def test_whitespace():
    with pytest.raises(ValueError):
        parse_quantity("")
    with pytest.raises(ValueError):
        parse_quantity(" ")
    with pytest.raises(ValueError):
        parse_quantity("1 ")
    with pytest.raises(ValueError):
        parse_quantity(" 1")
    with pytest.raises(ValueError):
        parse_quantity("1 Gi")


def test_canonical_equality_for_dicts_with_blanks():
    first = {}
    second = {}
    assert equals_canonically(first, second)

    first = {}
    second = None
    assert equals_canonically(first, second)


def test_canonical_equality_for_dicts_with_cpu():
    first = {"cpu": "0.5"}
    second = {"cpu": "500m"}
    assert equals_canonically(first, second)


def test_canonical_equality_for_dicts_with_memory():
    first = {"memory": "1G"}
    second = {"memory": "1Gi"}
    assert not equals_canonically(first, second)


def test_canonical_equality_for_dicts_with_both():
    first = {"cpu": "0.6", "memory": "1.5Gi"}
    second = {"cpu": "600m", "memory": "1536Mi"}
    assert equals_canonically(first, second)


def test_canonical_equality_for_extended_resources():
    first = {"cpu": "0.6", "example.com/foo": "1"}
    second = {"cpu": "600m", "example.com/foo": "1"}
    assert equals_canonically(first, second)

    first = {"cpu": "0.6", "example.com/foo": "1"}
    second = {"cpu": "600m", "example.com/foo": "2"}
    assert not equals_canonically(first, second)

    first = {"cpu": "0.6", "example.com/foo": "1"}
    second = {"cpu": "600m"}
    assert not equals_canonically(first, second)


def test_canonical_equality_for_resource_requirements_with_blanks():
    first = ResourceRequirements()
    second = ResourceRequirements()
    assert equals_canonically(first, second)

    first = ResourceRequirements(limits={})
    second = ResourceRequirements(limits={})
    assert equals_canonically(first, second)

    first = ResourceRequirements(limits={})
    second = ResourceRequirements(requests={})
    assert equals_canonically(first, second)


def test_canonical_equality_for_resource_requirements_with_cpu():
    first = ResourceRequirements(limits={"cpu": "0.5"})
    second = ResourceRequirements(limits={"cpu": "500m"})
    assert equals_canonically(first, second)

    first = ResourceRequirements(requests={"cpu": "0.5"})
    second = ResourceRequirements(requests={"cpu": "500m"})
    assert equals_canonically(first, second)

    first = ResourceRequirements(limits={"cpu": "0.5"})
    second = ResourceRequirements(requests={"cpu": "500m"})
    assert not equals_canonically(first, second)

    first = ResourceRequirements(limits={"cpu": "0.6"}, requests={"cpu": "0.5"})
    second = ResourceRequirements(limits={"cpu": "600m"}, requests={"cpu": "500m"})
    assert equals_canonically(first, second)


def test_canonical_equality_for_resource_requirements_with_memory():
    first = ResourceRequirements(limits={"memory": "1G"})
    second = ResourceRequirements(limits={"memory": "1Gi"})
    assert not equals_canonically(first, second)


def test_canonical_equality_for_resource_requirements_with_both():
    first = ResourceRequirements(limits={"cpu": "0.6", "memory": "1.5Gi"}, requests={"cpu": "0.5"})
    second = ResourceRequirements(limits={"cpu": "600m", "memory": "1536Mi"}, requests={"cpu": "500m"})
    assert equals_canonically(first, second)


def test_invalid_canonical_equality():
    with pytest.raises(TypeError):
        equals_canonically({}, ResourceRequirements())
    with pytest.raises(TypeError):
        equals_canonically(None, ResourceRequirements())
