from typing import List
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from lightkube.core.dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class B:
    b1: str
    b2: 'A' = None
    b3: 'dict' = None


@dataclass_json
@dataclass
class C:
    c1: str
    c2: List['A'] = None


@dataclass_json
@dataclass
class A:
    a1: str
    a2: int = 0
    a3: 'bool' = False


@dataclass_json
@dataclass
class DT:
    dt: 'datetime'


@pytest.mark.parametrize("lazy", [True, False])
def test_single(lazy):
    a = A.from_dict({'a1': 'a', 'a3': True}, lazy=lazy)
    assert a.a1 == 'a'
    assert a.a2 == 0
    assert a.a3 is True
    assert a.to_dict() == {'a1': 'a', 'a2': 0, 'a3': True}


@pytest.mark.parametrize("lazy", [True, False])
def test_nasted(lazy):
    b = B.from_dict({'b1': 'ok', 'b2': {'a1': 'a', 'a3': True}}, lazy=lazy)
    assert b.b1 == 'ok'
    if lazy:    # when we use lazy, sub-objects are not expanded yet
        assert 'b2' not in vars(b)
    else:
        assert 'b2' in vars(b)
    assert b.b2.a3 is True
    assert b.to_dict() == {'b1': 'ok', 'b2': {'a1': 'a', 'a2': 0, 'a3': True}}


@pytest.mark.parametrize("lazy", [True, False])
def test_nasted_in_list(lazy):
    c = C.from_dict({'c1': 'ok', 'c2': [{'a1': 'a', 'a3': True}, {'a1': 'b'}]}, lazy=lazy)
    if lazy:  # when we use lazy, sub-objects are not expanded yet
        assert 'c2' not in vars(c)
    else:
        assert 'c2' in vars(c)
    assert c.c2[0].a3 is True
    assert c.c2[1].a1 == 'b'
    assert c.to_dict() == {'c1': 'ok', 'c2': [
        {'a1': 'a', 'a2': 0, 'a3': True}, {'a1': 'b', 'a2': 0, 'a3': False}
    ]}


def test_nasted_to_dict():
    b = B.from_dict({'b1': 'ok', 'b2': {'a1': 'a', 'a3': True}}, lazy=True)
    assert b.to_dict() == {'b1': 'ok', 'b2': {'a1': 'a', 'a3': True}}


@pytest.mark.parametrize("lazy", [True, False])
def test_dict(lazy):
    b = B.from_dict({'b1': 'ok', 'b3': {'xx': 'x'}}, lazy=lazy)
    assert b.to_dict() == {'b1': 'ok', 'b3': {'xx': 'x'}}


def test_datatime():
    d = DT.from_dict({'dt': '2019-08-03T11:32:48Z'})
    assert d.dt == datetime(2019, 8, 3, 11, 32, 48, tzinfo=timezone.utc)
    assert d.to_dict() == {'dt': '2019-08-03T11:32:48Z'}

    d = DT.from_dict({'dt': '2019-08-03T11:32:48+02:30'})
    assert isinstance(d.dt, datetime) and str(d.dt) == '2019-08-03 11:32:48+02:30'
    assert d.to_dict() == {'dt': '2019-08-03T11:32:48+02:30'}
