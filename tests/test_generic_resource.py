import pytest
from unittest import mock

from lightkube import generic_resource as gr
from lightkube.core.generic_client import GenericClient
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apiextensions_v1 import CustomResourceDefinition
from lightkube.models.apiextensions_v1 import (
    CustomResourceDefinitionNames,
    CustomResourceDefinitionSpec,
    CustomResourceDefinitionVersion,
)


def create_dummy_crd(group="thisgroup", kind="thiskind", plural="thiskinds", scope="Namespaced",
                     versions=None):
    if versions is None:
        versions = ['v1alpha1', 'v1']

    crd = CustomResourceDefinition(
        spec=CustomResourceDefinitionSpec(
            group=group,
            names=CustomResourceDefinitionNames(
                kind=kind,
                plural=plural,
            ),
            scope=scope,
            versions=[
                CustomResourceDefinitionVersion(
                    name=version,
                    served=True,
                    storage=True,
                ) for version in versions
            ],
        )
    )

    return crd


@pytest.fixture()
def mocked_created_resources():
    """Isolates the module variable generic_resource._created_resources to avoid test spillover"""
    created_resources_dict = {}
    with mock.patch("lightkube.generic_resource._created_resources", created_resources_dict) as mocked_created_resources:
        yield mocked_created_resources


class MockedClient(GenericClient):
    def __init__(self):
        self.namespace = 'default'
        self._field_manager = None


@pytest.fixture()
def mocked_client_list_crds():
    """Yields a Client with a mocked .list which returns a fixed list of CRDs

    **returns**  Tuple of: mocked `Client`, list of CRDs, integer number of resources defined by
                 CRDs
    """
    scopes = ["Namespaced", "Cluster"]
    version_names = ['v2', 'v3']

    crds = [create_dummy_crd(scope=scope, kind=scope, versions=version_names) for scope in scopes]
    expected_n_resources = len(version_names) * len(crds)

    with mock.patch("lightkube.Client") as client_maker:
        mocked_client = mock.MagicMock()
        mocked_client.list.return_value = crds
        client_maker.return_value = mocked_client
        yield mocked_client, crds, expected_n_resources


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

    pr = c.prepare_request('post', obj=Test(metadata={'namespace': 'myns'}, spec={'a': 1}))
    assert pr.method == 'POST'
    assert pr.url == 'apis/test.eu/v1/namespaces/myns/tests'
    assert pr.data == {'apiVersion': 'test.eu/v1', 'kind': 'TestN', 'spec': {'a': 1}, 'metadata': {'namespace': 'myns'}}

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

    pr = c.prepare_request('post', obj=Test(spec={'a': 1}))
    assert pr.method == 'POST'
    assert pr.url == 'apis/test.eu/v1/tests'
    assert pr.data == {'apiVersion': 'test.eu/v1', 'kind': 'TestG', 'spec': {'a': 1}}

    pr = c.prepare_request('get', Test.Scale, name='xx')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/tests/xx/scale'

    pr = c.prepare_request('get', Test.Status, name='xx')
    assert pr.method == 'GET'
    assert pr.url == 'apis/test.eu/v1/tests/xx/status'


@pytest.mark.parametrize(
    "crd_scope",
    [
        "Namespaced",
        "Cluster",
    ]
)
def test_create_resources_from_crd(crd_scope, mocked_created_resources):
    version_names = ['v1alpha1', 'v1', 'v2']
    crd = create_dummy_crd(scope=crd_scope, versions=version_names)

    # Confirm no generic resources exist before testing
    assert len(gr._created_resources) == 0

    # Test the function
    gr.create_resources_from_crd(crd)

    # Confirm expected number of resources created
    assert len(gr._created_resources) == len(version_names)

    # Confirm expected resources exist
    for version in version_names:
        resource = gr.get_generic_resource(f"{crd.spec.group}/{version}", crd.spec.names.kind)
        assert resource is not None


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


def test_load_in_cluster_generic_resources(mocked_created_resources, mocked_client_list_crds):
    """Test that load_in_cluster_generic_resources creates generic resources for crds in cluster"""
    # Set up environment
    mocked_client, expected_crds, expected_n_resources = mocked_client_list_crds

    # Confirm no generic resources exist before testing
    assert len(gr._created_resources) == 0

    # Test the function
    gr.load_in_cluster_generic_resources(mocked_client)

    # Confirm the expected resources and no others were created
    assert len(gr._created_resources) == expected_n_resources
    for crd in expected_crds:
        for version in crd.spec.versions:
            resource = gr.get_generic_resource(f"{crd.spec.group}/{version.name}", crd.spec.names.kind)
            assert resource is not None

    mocked_client.list.assert_called_once()


def test_scale_model():
    """Test we are using the right model here"""
    Test = gr.create_global_resource('test.eu', 'v1', 'TestS', 'tests')
    a = Test.Scale.from_dict({'spec': {'replicas': 2}})
    assert a.spec.replicas == 2


def test_signature_change_not_allowed():
    gr.create_namespaced_resource('test.eu', 'v1', 'TestN', 'tests')
    gr.create_namespaced_resource('test.eu', 'v1', 'TestN', 'tests')

    with pytest.raises(ValueError, match='.*different signature'):
        gr.create_namespaced_resource('test.eu', 'v1', 'TestN', 'tests', verbs=['get'])

    with pytest.raises(ValueError, match='.*different signature'):
        gr.create_global_resource('test.eu', 'v1', 'TestN', 'tests')
