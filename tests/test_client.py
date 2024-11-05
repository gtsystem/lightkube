from collections import namedtuple
import unittest.mock
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import json
import pytest
import httpx
import respx

import lightkube
from lightkube.config.kubeconfig import KubeConfig, SingleConfig, Context, Cluster, User
from lightkube.resources.core_v1 import Pod, Node, Binding
from lightkube.models.meta_v1 import ObjectMeta
from lightkube import types
from lightkube.generic_resource import create_global_resource

KUBECONFIG = """
apiVersion: v1
clusters:
- cluster: {server: 'https://localhost:9443'}
  name: test
contexts:
- context: {cluster: test, user: test}
  name: test
current-context: test
kind: Config
preferences: {}
users:
- name: test
  user: {token: testtoken}
"""


def json_contains(json_str, data: dict):
    obj = json.loads(json_str)
    for key, value in data.items():
        assert key in obj
        assert obj[key] == value


@pytest.fixture
def kubeconfig(tmpdir):
    kubeconfig = tmpdir.join("kubeconfig")
    kubeconfig.write(KUBECONFIG)
    return kubeconfig


@pytest.fixture
def kubeconfig_ns(tmpdir):
    kubeconfig = tmpdir.join("kubeconfig")
    kubeconfig.write(KUBECONFIG.replace('user: test', 'user: test, namespace: ns1'))
    return kubeconfig


@pytest.fixture
def client(kubeconfig):
    config = KubeConfig.from_file(str(kubeconfig))
    return lightkube.Client(config=config)


def test_namespace(client: lightkube.Client, kubeconfig_ns):
    assert client.namespace == 'default'

    config = KubeConfig.from_file(str(kubeconfig_ns))
    client = lightkube.Client(config=config)
    assert client.namespace == 'ns1'


def test_client_config_attribute(kubeconfig):
    config = KubeConfig.from_file(kubeconfig)
    client = lightkube.Client(config=config)
    assert client.config == config.get()

    single_conf = config.get()
    client = lightkube.Client(config=single_conf)
    assert client.config is single_conf


@unittest.mock.patch('lightkube.core.generic_client.KubeConfig')
def test_client_default_config_construction(mock_kube_config):
    config = SingleConfig(
        context_name="test",
        context=Context(cluster='test', user="test"),
        cluster=Cluster(server="https://localhost:9443"),
        user=User(username="test"),
    )

    # config should be generated from environment without trust_env
    mock_kube_config.from_env.return_value.get.return_value = config
    lightkube.Client()
    mock_kube_config.from_env.assert_called_once_with()
    mock_kube_config.from_file.assert_not_called()

    # trust_env=False should create from DEFAULT_KUBECONFIG
    mock_kube_config.reset_mock()
    mock_kube_config.from_file.return_value.get.return_value = config
    lightkube.Client(trust_env=False)
    mock_kube_config.from_file.assert_called_once_with('~/.kube/config')
    mock_kube_config.from_env.assert_not_called()


@unittest.mock.patch('httpx.Client')
@unittest.mock.patch('lightkube.config.client_adapter.user_auth')
def test_client_httpx_attributes(user_auth, httpx_client, kubeconfig):
    config = KubeConfig.from_file(kubeconfig)
    single_conf = config.get()
    lightkube.Client(config=single_conf, trust_env=False)
    httpx_client.assert_called_once_with(
        timeout=None,
        base_url=single_conf.cluster.server,
        verify=True,
        cert=None,
        auth=user_auth.return_value,
        trust_env=False,
        transport=None,
    )


@respx.mock
def test_get_namespaced(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.get(Pod, name="xx")
    assert pod.metadata.name == 'xx'

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods/xx").respond(json={'metadata': {'name': 'xy'}})
    pod = client.get(Pod, name="xx", namespace="other")
    assert pod.metadata.name == 'xy'


@respx.mock
def test_get_global(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes/n1").respond(json={'metadata': {'name': 'n1'}})
    pod = client.get(Node, name="n1")
    assert pod.metadata.name == 'n1'

    # GET doesn't support all namespaces
    with pytest.raises(ValueError):
        client.get(Pod, name="xx", namespace=lightkube.ALL_NS)


@respx.mock
def test_list_namespaced(client: lightkube.Client):
    resp = {'items':[{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}]}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods").respond(json=resp)
    pods = client.list(Pod)
    for pod, expected in zip(pods, resp["items"]):
        assert pod.metadata is not None
        assert pod.metadata.name == expected["metadata"]["name"]
        assert pod.apiVersion is not None
        assert pod.kind is not None

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods?labelSelector=k%3Dv").respond(json=resp)
    pods = client.list(Pod, namespace="other", labels={'k': 'v'})
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']


@respx.mock
def test_list_crd(client: lightkube.Client):
    """CRD list seems to return always the 'continue' metadata attribute"""
    resp = {'items': [{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}], 'metadata': {'continue': ''}}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods").respond(json=resp)
    pods = client.list(Pod)
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']


@respx.mock
def test_list_global(client: lightkube.Client):
    resp = {'items': [{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}]}
    respx.get("https://localhost:9443/api/v1/nodes").respond(json=resp)
    nodes = client.list(Node)
    assert [node.metadata.name for node in nodes] == ['xx', 'yy']

    respx.get("https://localhost:9443/api/v1/pods?fieldSelector=k%3Dx").respond(json=resp)
    pods = client.list(Pod, namespace=lightkube.ALL_NS, fields={'k': 'x'})
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']

    # Binding doesn't support all namespaces
    with pytest.raises(ValueError):
        client.list(Binding, namespace=lightkube.ALL_NS)


@respx.mock
def test_list_chunk_size(client: lightkube.Client):
    resp = {'items': [{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}], 'metadata': {'continue': 'yes'}}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods?limit=3").respond(json=resp)
    resp = {'items': [{'metadata': {'name': 'zz'}}]}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods?limit=3&continue=yes").respond(json=resp)
    pods = client.list(Pod, chunk_size=3)
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy', 'zz']


@respx.mock
def test_delete_namespaced(client: lightkube.Client):
    respx.delete("https://localhost:9443/api/v1/namespaces/default/pods/xx")
    client.delete(Pod, name="xx")

    respx.delete("https://localhost:9443/api/v1/namespaces/other/pods/xx")
    client.delete(Pod, name="xx", namespace="other")

    # test grace_period parameter
    respx.delete("https://localhost:9443/api/v1/namespaces/default/pods/x_grace?gracePeriodSeconds=30")
    client.delete(Pod, name="x_grace", grace_period=30)

    # test cascade parameter
    respx.delete("https://localhost:9443/api/v1/namespaces/default/pods/x_cascade?propagationPolicy=Background")
    client.delete(Pod, name="x_cascade", cascade=types.CascadeType.BACKGROUND)

    # test dry_run parameter
    req_dry = respx.delete("https://localhost:9443/api/v1/namespaces/other/pods/z?dryRun=All")
    pod = client.delete(Pod, name="z", namespace="other", dry_run=True)
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'


@respx.mock
def test_delete_global(client: lightkube.Client):
    respx.delete("https://localhost:9443/api/v1/nodes/xx")
    client.delete(Node, name="xx")

    # test dry_run parameter
    req_dry = respx.delete("https://localhost:9443/api/v1/nodes/z?dryRun=All")
    node = client.delete(Node, name="z", dry_run=True)
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'

@respx.mock
def test_delete_collection_namespaced(client: lightkube.Client):

    # test dry_run parameter
    req_dry = respx.delete("https://localhost:9443/api/v1/namespaces/other/pods?dryRun=All")
    pod = client.deletecollection(Pod, namespace="other", dry_run=True)
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'

    respx.delete("https://localhost:9443/api/v1/namespaces/default/pods")
    client.deletecollection(Pod)

    respx.delete("https://localhost:9443/api/v1/namespaces/other/pods")
    client.deletecollection(Pod, namespace="other")

    # test grace_period parameter
    respx.delete("https://localhost:9443/api/v1/namespaces/grace/pods?gracePeriodSeconds=30")
    client.deletecollection(Pod, namespace="grace", grace_period=30)

    # test cascade parameter
    respx.delete("https://localhost:9443/api/v1/namespaces/cascade/pods?propagationPolicy=Orphan")
    client.deletecollection(Pod, namespace="cascade", cascade=types.CascadeType.ORPHAN)

@respx.mock
def test_deletecollection_global(client: lightkube.Client):
    # test dry_run parameter
    req_dry = respx.delete("https://localhost:9443/api/v1/nodes?dryRun=All")
    noeds = client.deletecollection(Node, dry_run=True)
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'

    respx.delete("https://localhost:9443/api/v1/nodes")
    client.deletecollection(Node)


@respx.mock
def test_errors(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx").respond(content="Error", status_code=409)
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx").respond(json={'message': 'got problems'},
              status_code=409)
    with pytest.raises(httpx.HTTPError):
        client.get(Pod, name="xx")

    with pytest.raises(lightkube.ApiError, match='got problems') as exc:
        client.get(Pod, name="xx")
    assert exc.value.status.message == 'got problems'


def make_watch_list(count=10):
    resp = "\n".join(
        json.dumps({'type': 'ADDED', 'object': {'metadata': {'name': f'p{i}', 'resourceVersion': '1'}}}) for i in
        range(count))
    return resp+"\n"


@respx.mock
def test_watch(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes?watch=true").respond(content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1").respond(status_code=404)

    i = None
    with pytest.raises(httpx.HTTPError) as exi:
        for i, (op, node) in enumerate(client.watch(Node)):
            assert node.metadata.name == f'p{i}'
            assert op == 'ADDED'
    assert i == 9
    assert exi.value.response.status_code == 404


@respx.mock
def test_watch_version(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=2&watch=true").respond(content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=1&watch=true").respond(status_code=404)

    # testing starting from specific resource version
    i = None
    with pytest.raises(httpx.HTTPError) as exi:
        for i, (op, node) in enumerate(client.watch(Node, resource_version="2")):
            assert node.metadata.name == f'p{i}'
            assert op == 'ADDED'
    assert i == 9
    assert exi.value.response.status_code == 404


@respx.mock
def test_watch_on_error(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes?watch=true").respond(content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1").respond(status_code=404)

    i = None
    for i, (op, node) in enumerate(client.watch(Node, on_error=types.on_error_stop)):
        assert node.metadata.name == f'p{i}'
        assert op == 'ADDED'
    assert i == 9


@respx.mock
def test_watch_stop_iter(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes?watch=true").respond(content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1").respond(status_code=404)

    i = None
    for i, _ in enumerate(client.watch(Node, on_error=types.on_error_raise)):
        break
    assert i == 0


def make_wait_success():
    states = [
        {
            "type": "ADDED",
            "object": {
                "metadata": {"name": "test-node", "resourceVersion": "1"},
                "status": None,
            },
        },
        {
            "type": "ADDED",
            "object": {
                "metadata": {"name": "test-node", "resourceVersion": "1"},
                "status": {"conditions": [{"type": "TestCondition", "status": "True"}]},
            },
        },
    ]

    return "\n".join(map(json.dumps, states))


def make_wait_deleted():
    state = {
        "type": "DELETED",
        "object": {
            "metadata": {"name": "test-node", "resourceVersion": "1"},
            "status": {},
        },
    }

    return json.dumps(state)


def make_wait_failed():
    state = {
        "type": "ADDED",
        "object": {
            "metadata": {"name": "test-node", "resourceVersion": "1"},
            "status": {"conditions": [{"type": "TestCondition", "status": "True"}]},
        },
    }

    return json.dumps(state)


def make_wait_custom():
    state = {
        "type": "ADDED",
        "object": {
            "metadata": {"name": "custom-resource", "resourceVersion": "1"},
            "status": {"conditions": [{"type": "TestCondition", "status": "True"}]},
        },
    }

    return json.dumps(state)


@respx.mock
def test_wait_success(client: lightkube.Client):
    base_url = "https://localhost:9443/api/v1/nodes?fieldSelector=metadata.name%3Dtest-node&watch=true"

    respx.get(base_url).respond(content=make_wait_success())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_success())

    node = client.wait(Node, "test-node", for_conditions=["TestCondition"])

    assert node.to_dict()["metadata"]["name"] == "test-node"


@respx.mock
def test_wait_deleted(client: lightkube.Client):
    base_url = "https://localhost:9443/api/v1/nodes?fieldSelector=metadata.name%3Dtest-node&watch=true"

    respx.get(base_url).respond(content=make_wait_deleted())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_deleted())

    message = "nodes/test-node was unexpectedly deleted"
    with pytest.raises(lightkube.core.exceptions.ObjectDeleted, match=message):
        client.wait(Node, "test-node", for_conditions=["TestCondition"])


@respx.mock
def test_wait_failed(client: lightkube.Client):
    base_url = "https://localhost:9443/api/v1/nodes?fieldSelector=metadata.name%3Dtest-node&watch=true"

    respx.get(base_url).respond(content=make_wait_failed())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_failed())

    message = r"nodes/test-node has failure condition\(s\): TestCondition"
    with pytest.raises(lightkube.core.exceptions.ConditionError, match=message):
        client.wait(Node, "test-node", for_conditions=[], raise_for_conditions=["TestCondition"])


@respx.mock
def test_wait_custom(client: lightkube.Client):
    base_url = "https://localhost:9443/apis/custom.org/v1/customs?fieldSelector=metadata.name%3Dcustom-resource&watch=true"

    Custom = create_global_resource(
        group="custom.org", version="v1", kind="Custom", plural="customs"
    )
    respx.get(base_url).respond(content=make_wait_custom())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_custom())

    client.wait(Custom, "custom-resource", for_conditions=["TestCondition"])


@respx.mock
def test_patch_namespaced(client: lightkube.Client):
    # Default PatchType.STRATEGIC
    req = respx.patch("https://localhost:9443/api/v1/namespaces/default/pods/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.patch(Pod, "xx", Pod(metadata=ObjectMeta(labels={'l': 'ok'})))
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/strategic-merge-patch+json"

    # PatchType.MERGE
    req = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.patch(Pod, "xx", Pod(metadata=ObjectMeta(labels={'l': 'ok'})), namespace='other',
                       patch_type=types.PatchType.MERGE, force=True)
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/merge-patch+json"
    assert 'force' not in str(req.calls[0][0].url)  # force is ignored for non APPLY patch types

    # PatchType.APPLY
    req = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xy?fieldManager=test").respond(
        json={'metadata': {'name': 'xy'}})
    pod = client.patch(Pod, "xy", Pod(metadata=ObjectMeta(labels={'l': 'ok'})), namespace='other',
                       patch_type=types.PatchType.APPLY, field_manager='test')
    assert pod.metadata.name == 'xy'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # PatchType.APPLY + force
    req = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xz?fieldManager=test&force=true").respond(
        json={'metadata': {'name': 'xz'}})
    pod = client.patch(Pod, "xz", Pod(metadata=ObjectMeta(labels={'l': 'ok'})), namespace='other',
                       patch_type=types.PatchType.APPLY, field_manager='test', force=True)
    assert pod.metadata.name == 'xz'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # PatchType.APPLY without field_manager
    with pytest.raises(ValueError, match="field_manager"):
        client.patch(Pod, "xz", Pod(metadata=ObjectMeta(labels={'l': 'ok'})), namespace='other',
                     patch_type=types.PatchType.APPLY)

    # test dry_run parameter
    req_dry = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xz?fieldManager=test&dryRun=All").respond(
        json={'metadata': {'name': 'xz'}})
    node = client.patch(Pod, "xz", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
        patch_type=types.PatchType.STRATEGIC, namespace="other",  field_manager='test', dry_run=True)
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'


@respx.mock
def test_patch_global(client: lightkube.Client):
    req = respx.patch("https://localhost:9443/api/v1/nodes/xx").respond(json={'metadata': {'name': 'xx'}})
    node = client.patch(Node, "xx", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
                        patch_type=types.PatchType.JSON)
    assert node.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/json-patch+json"

    # PatchType.APPLY + force
    req = respx.patch("https://localhost:9443/api/v1/nodes/xy?fieldManager=test&force=true").respond(
        json={'metadata': {'name': 'xy'}})
    node = client.patch(Node, "xy", Pod(metadata=ObjectMeta(labels={'l': 'ok'})),
                        patch_type=types.PatchType.APPLY, field_manager='test', force=True)
    assert node.metadata.name == 'xy'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # test dry_run parameter
    req_dry = respx.patch("https://localhost:9443/api/v1/nodes/xz?fieldManager=test&dryRun=All").respond(
        json={'metadata': {'name': 'xz'}})
    node = client.patch(Node, "xz", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
        patch_type=types.PatchType.APPLY, field_manager='test', dry_run=True)
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'


@respx.mock
def test_field_manager(kubeconfig):
    config = KubeConfig.from_file(str(kubeconfig))
    client = lightkube.Client(config=config, field_manager='lightkube')
    respx.patch("https://localhost:9443/api/v1/nodes/xx?fieldManager=lightkube").respond(json={'metadata': {'name': 'xx'}})
    client.patch(Node, "xx", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
                       patch_type=types.PatchType.JSON)

    respx.post("https://localhost:9443/api/v1/namespaces/default/pods?fieldManager=lightkube").respond(json={'metadata': {'name': 'xx'}})
    client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'})))

    respx.put("https://localhost:9443/api/v1/namespaces/default/pods/xy?fieldManager=lightkube").respond(
        json={'metadata': {'name': 'xy'}})
    client.replace(Pod(metadata=ObjectMeta(name="xy")))

    respx.put("https://localhost:9443/api/v1/namespaces/default/pods/xy?fieldManager=override").respond(
        json={'metadata': {'name': 'xy'}})
    client.replace(Pod(metadata=ObjectMeta(name="xy")), field_manager='override')


@respx.mock
def test_create_namespaced(client: lightkube.Client):
    req = respx.post("https://localhost:9443/api/v1/namespaces/default/pods").respond(json={'metadata': {'name': 'xx'}})
    pod = client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'})))
    json_contains(req.calls[0][0].read(), {"metadata": {"labels": {"l": "ok"}, "name": "xx"}})
    assert pod.metadata.name == 'xx'

    req2 = respx.post("https://localhost:9443/api/v1/namespaces/other/pods").respond(json={'metadata': {'name': 'yy'}})
    pod = client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'})), namespace='other')
    assert pod.metadata.name == 'yy'
    json_contains(req2.calls[0][0].read(), {"metadata": {"labels": {"l": "ok"}, "name": "xx"}})

    respx.post("https://localhost:9443/api/v1/namespaces/ns2/pods").respond(
        json={'metadata': {'name': 'yy'}})
    pod = client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'}, namespace='ns2')))
    assert pod.metadata.name == 'yy'

    # namespace inside object definition need to match with provided namespace parameter.
    with pytest.raises(ValueError):
        client.create(Pod(metadata=ObjectMeta(name="xx", namespace='ns1')), namespace='ns2')


@respx.mock
def test_create_global(client: lightkube.Client):
    req = respx.post("https://localhost:9443/api/v1/nodes").respond(json={'metadata': {'name': 'xx'}})
    pod = client.create(Node(metadata=ObjectMeta(name="xx")))
    json_contains(req.calls[0][0].read(), {"metadata": {"name": "xx"}})
    assert pod.metadata.name == 'xx'

    # dry-run
    req_dry = respx.post("https://localhost:9443/api/v1/nodes").respond(
        json={'metadata': {'name': 'xz'}})
    node = client.create(Node(metadata=ObjectMeta(name='xz')), dry_run=True)
    assert req_dry.calls[1][0].url.params['dryRun'] == 'All'

@respx.mock
def test_replace_namespaced(client: lightkube.Client):
    req = respx.put("https://localhost:9443/api/v1/namespaces/default/pods/xy").respond(json={'metadata': {'name': 'xy'}})
    pod = client.replace(Pod(metadata=ObjectMeta(name="xy")))
    json_contains(req.calls[0][0].read(), {"metadata": {"name": "xy"}})
    assert pod.metadata.name == 'xy'

    respx.put("https://localhost:9443/api/v1/namespaces/other/pods/xz").respond(json={'metadata': {'name': 'xz'}})
    pod = client.replace(Pod(metadata=ObjectMeta(name="xz")), namespace='other')
    assert pod.metadata.name == 'xz'

    # namespace inside object definition need to match with provided namespace parameter.
    with pytest.raises(ValueError):
        client.replace(Pod(metadata=ObjectMeta(name="xx", namespace='ns1')), namespace='ns2')

    # dry-run
    req_dry = respx.put("https://localhost:9443/api/v1/namespaces/other/pods/xx").respond(
        json={'metadata': {'name': 'xx'}})
    pod = client.replace(Pod(metadata=ObjectMeta(name='xx')), namespace="other", dry_run=True)
    assert pod.metadata.name == 'xx'
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'

@respx.mock
def test_replace_global(client: lightkube.Client):
    req = respx.put("https://localhost:9443/api/v1/nodes/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.replace(Node(metadata=ObjectMeta(name="xx")))
    json_contains(req.calls[0][0].read(), {"metadata": {"name": "xx"}, "apiVersion": "v1", "kind": "Node"})
    assert pod.metadata.name == 'xx'

    # dry-run
    req_dry = respx.put("https://localhost:9443/api/v1/nodes/xy").respond(
        json={'metadata': {'name': 'xy'}})
    pod = client.replace(Node(metadata=ObjectMeta(name='xy')), dry_run=True)
    assert req_dry.calls[0][0].url.params['dryRun'] == 'All'


@respx.mock
def test_pod_log(client: lightkube.Client):
    result = ['line1\n', 'line2\n', 'line3\n']
    content = "".join(result)

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log").respond(content=content)
    lines = list(client.log('test'))
    assert lines == result

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log?follow=true").respond(
        content=content)
    lines = list(client.log('test', follow=True))
    assert lines == result

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log?tailLines=3").respond(
        content=content)
    lines = list(client.log('test', tail_lines=3))
    assert lines == result

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log?since=30&timestamps=true").respond(
        content=content)
    lines = list(client.log('test', since=30, timestamps=True))
    assert lines == result

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log?container=bla").respond(
        content=content)

    lines = list(client.log('test', container="bla", newlines=False))
    assert lines == [_.strip() for _ in result]

    lines = list(client.log('test', container="bla"))
    assert lines == result


@respx.mock
def test_apply_namespaced(client: lightkube.Client):
    req = respx.patch("https://localhost:9443/api/v1/namespaces/default/pods/xy?fieldManager=test").respond(
        json={'metadata': {'name': 'xy'}})
    pod = client.apply(Pod(metadata=ObjectMeta(name='xy')), field_manager='test')
    assert pod.metadata.name == 'xy'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # custom namespace, force
    req = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xz?fieldManager=a&force=true").respond(
        json={'metadata': {'name': 'xz'}})
    pod = client.apply(Pod(metadata=ObjectMeta(name='xz', namespace='other')), field_manager='a', force=True)
    assert pod.metadata.name == 'xz'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # sub-resource
    req = respx.patch("https://localhost:9443/api/v1/namespaces/default/pods/xx/status?fieldManager=a").respond(
        json={'metadata': {'name': 'xx'}})
    pod = client.apply(Pod.Status(), name='xx', field_manager='a')
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"


@respx.mock
def test_apply_global(client: lightkube.Client):
    req = respx.patch("https://localhost:9443/api/v1/nodes/xy?fieldManager=test").respond(
        json={'metadata': {'name': 'xy'}})
    node = client.apply(Node(metadata=ObjectMeta(name='xy')), field_manager='test')
    assert node.metadata.name == 'xy'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # sub-resource + force
    req = respx.patch("https://localhost:9443/api/v1/nodes/xx/status?fieldManager=a&force=true").respond(
        json={'metadata': {'name': 'xx'}})
    node = client.apply(Node.Status(), name='xx', field_manager='a', force=True)
    assert node.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # dry-run
    req = respx.patch("https://localhost:9443/api/v1/nodes/xz?fieldManager=test&dryRun=All").respond(
        json={'metadata': {'name': 'xz'}})
    node = client.apply(Node(metadata=ObjectMeta(name='xz')), field_manager='test', dry_run=True)
    assert node.metadata.name == 'xz'
    assert req.calls[0][0].url.params['dryRun'] == 'All'

