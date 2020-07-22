from typing import Dict
from collections.abc import Iterable
from lightkube import operators


def build_selector(pairs: Dict):
    res = []
    for k, v in pairs.items():
        if v is None:
            v = operators.exist()
        elif isinstance(v, str):
            v = operators.equal(v)
        elif isinstance(v, Iterable):
            v = operators.in_(v)

        if not isinstance(v, operators.Operator):
            raise ValueError(f"selector value '{v}' should be str, None, Iterable or instance of operator")
        res.append(v.encode(k))
    return ','.join(res)
