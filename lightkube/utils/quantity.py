import decimal
import re
from typing import Optional, overload

from ..core.internal_models import core_v1

ResourceRequirements = core_v1.ResourceRequirements

MULTIPLIERS = {
    # Bytes
    "m": (10, -3),  # 1000^(-1) (=0.001)
    "": (10, 0),  # 1000^0 (=1)
    "k": (10, 3),  # 1000^1
    "M": (10, 6),  # 1000^2
    "G": (10, 9),  # 1000^3
    "T": (10, 12),  # 1000^4
    "P": (10, 15),  # 1000^5
    "E": (10, 18),  # 1000^6
    "Z": (10, 21),  # 1000^7
    "Y": (10, 24),  # 1000^8

    # Bibytes
    "Ki": (1024, 1),  # 2^10
    "Mi": (1024, 2),  # 2^20
    "Gi": (1024, 3),  # 2^30
    "Ti": (1024, 4),  # 2^40
    "Pi": (1024, 5),  # 2^50
    "Ei": (1024, 6),  # 2^60
    "Zi": (1024, 7),  # 2^70
    "Yi": (1024, 8),  # 2^80
}

# Pre-calculate multipliers and store as decimals.
MULTIPLIERS = {k: decimal.Decimal(v[0])**v[1] for k, v in MULTIPLIERS.items()}


def parse_quantity(quantity: Optional[str]) -> Optional[decimal.Decimal]:
    """Parse a quantity string into a bare (suffix-less) decimal.

    Kubernetes converts user input to a canonical representation. For example, "0.9Gi" would be converted
    to "966367641600m".
    This function can be useful for comparing user input to actual values, for example comparing
    resource limits between a StatefulSet's template
    (`statefulset.spec.template.spec.containers[i].resources`) and a scheduled pod
    (`pod.spec.containers[i].resources`) after patching the StatefulSet.

    **Parameters**

    * **quantity** `str` - An str representing a K8s quantity (e.g. "1Gi" or "1G"), per
    https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/quantity/.

    **returns**  An instance of `decimal.Decimal` representing the quantity as a bare decimal.
    """
    if quantity is None:
        # This is useful for comparing e.g. ResourceRequirements.limits.get("cpu"), which can be
        # None.
        return None

    pat = re.compile(r"([+-]?\d+(?:[.]\d*)?(?:e[+-]?\d+)?|[.]\d+(?:e[+-]?\d+)?)(.*)")
    match = pat.match(quantity)

    if not match:
        raise ValueError("Invalid quantity string: '{}'".format(quantity))

    try:
        value = decimal.Decimal(match.group(1))
    except ArithmeticError as e:
        raise ValueError("Invalid numerical value") from e

    unit = match.group(2)

    try:
        multiplier = MULTIPLIERS[unit]
    except KeyError:
        raise ValueError("Invalid unit suffix: {}".format(unit))

    try:
        as_decimal = value * multiplier
        return as_decimal.quantize(decimal.Decimal("0.001"), rounding=decimal.ROUND_UP)
    except ArithmeticError as e:
        raise ValueError("Invalid numerical value") from e


def _equals_canonically(first_dict: Optional[dict], second_dict: Optional[dict]) -> bool:
    """Compare resource dicts such as 'limits' or 'requests'."""
    if first_dict == second_dict:
        # This covers two cases: (1) both args are None; (2) both args are identical dicts.
        return True
    if first_dict and second_dict:
        if first_dict.keys() != second_dict.keys():
            # The dicts have different keys, so they cannot possibly be equal
            return False
        return all(
            parse_quantity(first_dict[k]) == parse_quantity(second_dict[k])
            for k in first_dict.keys()
        )
    if not first_dict and not second_dict:
        # This covers cases such as first=None and second={}
        return True
    return False


@overload
def equals_canonically(first: ResourceRequirements, second: ResourceRequirements) -> bool:
    ...


@overload
def equals_canonically(first: Optional[dict], second: Optional[dict]) -> bool:
    ...


def equals_canonically(first, second):
    """Compare two resource requirements for numerical equality.

    Both arguments must be of the same type and can be either:

    - An instance of `core_v1.ResourceRequirements`
    - `Optional[dict]`: representing the "limits" or the "requests" portion of `ResourceRequirements`.

    ```python
    >>> equals_canonically({"cpu": "0.6"}, {"cpu": "600m"})
    True

    >>> equals_canonically(
            ResourceRequirements(limits={"cpu": "0.6"}),
            ResourceRequirements(limits={"cpu": "600m"})
        )
    True
    ```

    **Parameters**

    * **first** `ResourceRequirements` or `dict` - The first item to compare.
    * **second** `ResourceRequirements` or `dict` - The second item to compare.

    **returns**  True, if both arguments are numerically equal; False otherwise.
    """
    if isinstance(first, (dict, type(None))) and isinstance(second, (dict, type(None))):
        # Args are 'limits' or 'requests' dicts
        return _equals_canonically(first, second)
    elif isinstance(first, ResourceRequirements) and isinstance(second, ResourceRequirements):
        # Args are ResourceRequirements, which may contain 'limits' and 'requests' dicts
        ks = ("limits", "requests")
        return all(_equals_canonically(getattr(first, k), getattr(second, k)) for k in ks)
    else:
        raise TypeError("unsupported operand type(s) for canonical comparison: '{}' and '{}'".format(
            first.__class__.__name__, second.__class__.__name__,
        ))
