from typing import Dict
from collections.abc import Iterable
from lightkube import operators


def build_selector(pairs: Dict, binaryOnly=False):
    res = []
    for k, v in pairs.items():
        if v is None:
            v = operators.exists()
        elif isinstance(v, str):
            v = operators.equal(v)
        elif isinstance(v, Iterable):
            v = operators.in_(v)

        if not isinstance(v, operators.Operator):
            raise ValueError(f"selector value '{v}' should be str, None, Iterable or instance of operator")

        if binaryOnly and not isinstance(v, operators.BinaryOperator):
            raise ValueError("parameter 'fields' only support values of type str or operators.BinaryOperator")
        res.append(v.encode(k))
    return ','.join(res)
