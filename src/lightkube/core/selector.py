from typing import Any, Dict, Iterable, List, Tuple, Union

from lightkube import operators

FIELDS_SUPPORT = ("equal", "not_equal", "not_in")
FIELDS_SUPPORT_STR = ", ".join(f'"{fs}"' for fs in FIELDS_SUPPORT)

_VALUE_TYPE = Union[None, str, operators.Operator[Any], Iterable[str]]


def build_selector(pairs: Union[List[Tuple[str, _VALUE_TYPE]], Dict[str, _VALUE_TYPE]], for_fields: bool = False) -> str:
    res = []
    pairs_it: Iterable[Tuple[str, _VALUE_TYPE]]
    if not isinstance(pairs, list):
        pairs_it = pairs.items()
    else:
        pairs_it = pairs
    for k, v in pairs_it:
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

        if for_fields and v.op_name == "not_in":  # not_in can be implement using several !=
            assert isinstance(v, operators.SequenceOperator)
            for item in v.value:
                res.append(operators.not_equal(item).encode(k))
        else:
            res.append(v.encode(k))
    return ",".join(res)
