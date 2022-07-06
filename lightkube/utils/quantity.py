import decimal
import re
from typing import Optional


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

    K8s converts user input to a canonical representation. For example, "0.9Gi" would be converted
    to "966367641600m".
    This function can be useful for comparing user input to actual values, for example comparing
    resource limits between a statefulset's template
    (statefulset.spec.template.spec.containers[i].resources) and a scheduled pod
    (pod.spec.containers[i].resources) after patching the statefulset.

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
