import pytest

from lightkube import generic_resource as gr
from lightkube.core.generic_client import GenericClient
from lightkube.models.meta_v1 import ObjectMeta

class MockedClient(GenericClient):
    def __init__(self):
        self.namespace = 'default'


def test_create_namespaced_resource():
    c = MockedClient()
    Test = gr.create_namespaced_resource('test.eu', 'v1', 'TestN', 'tests')
    assert Test.__name__ == 'TestN'

    pr = c.prepare_request('get', Test, name='xx', namespace='myns')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/namespaces/myns/tests/xx'

    pr = c.prepare_request('list', Test, namespace='myns')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/namespaces/myns/tests'

    pr = c.prepare_request('get', Test.Scale, name='xx', namespace='myns')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/namespaces/myns/tests/xx/scale'

    pr = c.prepare_request('get', Test.Status, name='xx', namespace='myns')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/namespaces/myns/tests/xx/status'


def test_create_global_resource():
    c = MockedClient()
    Test = gr.create_global_resource('test.eu', 'v1', 'TestG', 'tests')
    assert Test.__name__ == 'TestG'

    pr = c.prepare_request('get', Test, name='xx')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/tests/xx'

    pr = c.prepare_request('list', Test)
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/tests'

    pr = c.prepare_request('get', Test.Scale, name='xx')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/tests/xx/scale'

    pr = c.prepare_request('get', Test.Status, name='xx')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/tests/xx/status'


def test_generic_model():
    mod = gr.Generic.from_dict({'metadata': {'name': 'bla'}, 'test': {'ok': 4}})
    assert mod.metadata.name == 'bla'
    assert mod.test['ok'] == 4
    assert mod.to_dict() == {'metadata': {'name': 'bla'}, 'test': {'ok': 4}}
    assert mod.status is None

    mod = gr.Generic.from_dict({'apiVersion': 'v1', 'kind': 'Test', 'status': 1})
    assert mod.apiVersion == 'v1'
    assert mod.kind == 'Test'
    assert mod.metadata is None
    assert mod.to_dict() == {'apiVersion': 'v1', 'kind': 'Test', 'status': 1}
    assert mod.status == 1

    mod = gr.Generic(metadata=ObjectMeta(name='bla'), test={'ok': 4})
    assert mod.metadata.name == 'bla'
    assert mod.test['ok'] == 4
    assert mod.to_dict() == {'metadata': {'name': 'bla'}, 'test': {'ok': 4}}
    assert mod.status is None

    with pytest.raises(AttributeError):
        mod._a


def test_scale_model():
    """Test we are using the right model here"""
    Test = gr.create_global_resource('test.eu', 'v1', 'TestS', 'tests')
    a = Test.Scale.from_dict({'spec': {'replicas': 2}})
    assert a.spec.replicas == 2
