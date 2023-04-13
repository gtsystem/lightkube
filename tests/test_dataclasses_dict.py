from typing import List
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from lightkube.core.dataclasses_dict import DataclassDictMixIn


@dataclass
class B(DataclassDictMixIn):
    b1: str
    b2: 'A' = None
    b3: 'dict' = None


@dataclass
class C(DataclassDictMixIn):
    c1: str
    c2: List['A'] = None
    c3: str = field(metadata={"json": "$ref"}, default=None)


@dataclass
class A(DataclassDictMixIn):
    a1: str
    a2: int = 0
    a3: 'bool' = False


@dataclass
class DT(DataclassDictMixIn):
    dt: 'datetime'


@dataclass
class Def(DataclassDictMixIn):
    d1: str
    d2: int = 2
    d3: 'bool' = False
    d4: str = "ok"


@pytest.mark.parametrize("lazy", [True, False])
def test_issue_44(lazy):
    inst = C.from_dict({"c1": "val"}, lazy=lazy)                    # Setup a C object without setting c2
    assert inst.to_dict() == {"c1": "val"}                          # de-serialize to a dict
    inst.c2 = [A("abc")]                                            # Add c2 list
    assert inst.to_dict() == {"c1": "val", "c2": [{"a1": "abc"}]}   # Expect c2 list to show up in dict


@pytest.mark.parametrize("lazy", [True, False])
def test_single(lazy):
    a = A.from_dict({'a1': 'a', 'a3': True}, lazy=lazy)
    assert a.a1 == 'a'
    assert a.a2 == 0
    assert a.a3 is True
    assert a.to_dict() == {'a1': 'a', 'a3': True}


@pytest.mark.parametrize("lazy", [True, False])
def test_nasted(lazy):
    b = B.from_dict({'b1': 'ok', 'b2': {'a1': 'a', 'a3': True}}, lazy=lazy)
    assert b.b1 == 'ok'
    if lazy:    # when we use lazy, sub-objects are not expanded yet
        assert 'b2' not in vars(b)
    else:
        assert 'b2' in vars(b)
    assert b.b2.a3 is True
    assert b.to_dict() == {'b1': 'ok', 'b2': {'a1': 'a', 'a3': True}}


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
        {'a1': 'a', 'a3': True}, {'a1': 'b'}
    ]}


def test_nasted_to_dict():
    b = B.from_dict({'b1': 'ok', 'b2': {'a1': 'a', 'a3': True}}, lazy=True)
    assert b.to_dict() == {'b1': 'ok', 'b2': {'a1': 'a', 'a3': True}}


@pytest.mark.parametrize("lazy", [True, False])
def test_dict(lazy):
    b = B.from_dict({'b1': 'ok', 'b3': {'xx': 'x'}}, lazy=lazy)
    assert b.to_dict() == {'b1': 'ok', 'b3': {'xx': 'x'}}


def test_datatime():
    """Datetime get converted to string and back"""
    d = DT.from_dict({'dt': '2019-08-03T11:32:48Z'})
    assert d.dt == datetime(2019, 8, 3, 11, 32, 48, tzinfo=timezone.utc)
    assert d.to_dict() == {'dt': '2019-08-03T11:32:48Z'}

    d = DT.from_dict({'dt': '2019-08-03T11:32:48+02:30'})
    assert isinstance(d.dt, datetime) and str(d.dt) == '2019-08-03 11:32:48+02:30'
    assert d.to_dict() == {'dt': '2019-08-03T11:32:48+02:30'}


@pytest.mark.parametrize("lazy", [True, False])
def test_rename(lazy):
    """We can rename fields from/to dicts"""
    c = C.from_dict({'c1': 'a', '$ref': 'b'}, lazy=lazy)
    assert c.c1 == 'a'
    assert c.c3 == 'b'
    c.c3 = 'c'

    assert c.to_dict() == {'c1': 'a', '$ref': 'c'}


@pytest.mark.parametrize("lazy", [True, False])
def test_drop_unknown(lazy):
    """Unknown attributes are dropped"""
    c = C.from_dict({'c1': 'a', 'k': 'b'}, lazy=lazy)
    assert c.c1 == 'a'
    assert not hasattr(c, 'k')

    assert c.to_dict() == {'c1': 'a'}


def test_default_not_encoded():
    """Test that default values are not returned in the dict"""
    assert Def(d1='a').to_dict() == {'d1': 'a'}
    assert Def(d1='a', d2=2).to_dict() == {'d1': 'a'}
    assert Def(d1='a', d2=0).to_dict() == {'d1': 'a', 'd2': 0}
    assert Def(d1='a', d3=False).to_dict() == {'d1': 'a'}
    assert Def(d1='a', d3=True).to_dict() == {'d1': 'a', 'd3': True}
    assert Def(d1='a', d4='ok').to_dict() == {'d1': 'a'}
    assert Def(d1='a', d4='ko').to_dict() == {'d1': 'a', 'd4': 'ko'}
