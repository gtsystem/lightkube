import pytest

from lightkube.codecs import resource_registry
from lightkube.resources.core_v1 import Pod
from lightkube.resources.apps_v1 import Deployment
from lightkube.resources.events_v1 import Event
from lightkube.core import resource as res

@pytest.fixture(autouse=True)
def cleanup_registry():
    """Cleanup the registry after each test"""
    yield
    resource_registry.clear()

@pytest.mark.parametrize(
    "version,kind,Res",
    [("v1", "Pod", Pod), ("apps/v1", "Deployment", Deployment), ("events.k8s.io/v1", "Event", Event)]
)
def test_register(version, kind, Res):
    assert resource_registry.get(version, kind) is None
    res = resource_registry.register(Res)
    assert res is Res
    assert resource_registry.get(version, kind) is Res


def test_register_decorator():
    assert resource_registry.get("test.io/v1", "Search") is None

    @resource_registry.register
    class Search(res.NamespacedResource):
        _api_info = res.ApiInfo(
            resource=res.ResourceDef('test.io', 'v1', 'Search'),
            plural='searches',
            verbs=['delete', 'deletecollection', 'get', 'global_list', 'global_watch', 'list', 'patch', 'post', 'put',
                   'watch']
        )

    assert resource_registry.get("test.io/v1", "Search") is Search


@pytest.mark.parametrize(
    "version,kind,Res",
    [("v1", "Pod", Pod), ("apps/v1", "Deployment", Deployment), ("events.k8s.io/v1", "Event", Event)]
)
def test_load(version, kind, Res):
    assert resource_registry.get(version, kind) is None
    pod_class = resource_registry.load(version, kind)
    assert pod_class is Res
    assert resource_registry.get(version, kind) is Res
