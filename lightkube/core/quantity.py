import decimal
import re

multipliers = {
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


def parse_quantity(quantity: str) -> decimal.Decimal:
    """Parse a quantity string into bytes.

    Reference: https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/quantity/
    """
    pat = re.compile(r"([+-]?\d+(?:[.]\d*)?(?:e[+-]?\d+)?|[.]\d+(?:e[+-]?\d+)?)(.*)")
    match = pat.match(quantity)

    if not match:
        raise ValueError("Invalid quantity string: {}".format(quantity))

    try:
        value = decimal.Decimal(match.group(1))
    except ArithmeticError as e:
        raise ValueError("Invalid numerical value") from e

    unit = match.group(2)

    try:
        base, exp = multipliers[unit]
    except KeyError:
        raise ValueError("Invalid unit suffix: {}".format(unit))

    as_bytes = value * base ** exp
    return as_bytes.quantize(decimal.Decimal("0.001"), rounding=decimal.ROUND_UP)
