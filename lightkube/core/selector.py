from typing import Dict, Union, List
from collections.abc import Iterable
from lightkube import operators

FIELDS_SUPPORT = ('equal', 'not_equal', 'not_in')
FIELDS_SUPPORT_STR = ', '.join(f'"{fs}"' for fs in FIELDS_SUPPORT)


def build_selector(pairs: Union[List, Dict], for_fields=False):
    res = []
    if not isinstance(pairs, list):
        pairs = pairs.items()
    for k, v in pairs:
        if v is None:
            v = operators.exists()
        elif isinstance(v, str):
            v = operators.equal(v)
        elif isinstance(v, Iterable):
            v = operators.in_(v)

        if not isinstance(v, operators.Operator):
            raise ValueError(f"selector value '{v}' should be str, None, Iterable or instance of operator")

        if for_fields and v.op_name not in FIELDS_SUPPORT:
            raise ValueError(f"parameter 'fields' only support operators {FIELDS_SUPPORT_STR}")

        if for_fields and v.op_name == 'not_in':    # not_in can be implement using several !=
            for item in v.value:
                res.append(operators.not_equal(item).encode(k))
        else:
            res.append(v.encode(k))
    return ','.join(res)
