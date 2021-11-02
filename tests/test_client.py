import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import json
import pytest
import httpx
import respx

import lightkube
from lightkube.config.kubeconfig import KubeConfig
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
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods?labelSelector=k%3Dv").respond(json=resp)
    pods = client.list(Pod, namespace="other", labels={'k': 'v'})
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


@respx.mock
def test_delete_global(client: lightkube.Client):
    respx.delete("https://localhost:9443/api/v1/nodes/xx")
    client.delete(Node, name="xx")


@respx.mock
def test_delete_collection_namespaced(client: lightkube.Client):
    respx.delete("https://localhost:9443/api/v1/namespaces/default/pods")
    client.deletecollection(Pod)

    respx.delete("https://localhost:9443/api/v1/namespaces/other/pods")
    client.deletecollection(Pod, namespace="other")


@respx.mock
def test_deletecollection_global(client: lightkube.Client):
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
    req = respx.patch("https://localhost:9443/api/v1/namespaces/default/pods/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.patch(Pod, "xx", Pod(metadata=ObjectMeta(labels={'l': 'ok'})))
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/strategic-merge-patch+json"

    req = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.patch(Pod, "xx", Pod(metadata=ObjectMeta(labels={'l': 'ok'})), namespace='other',
                       patch_type=types.PatchType.MERGE)
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/merge-patch+json"


@respx.mock
def test_patch_global(client: lightkube.Client):
    req = respx.patch("https://localhost:9443/api/v1/nodes/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.patch(Node, "xx", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
                       patch_type=types.PatchType.JSON)
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/json-patch+json"


@respx.mock
def test_create_namespaced(client: lightkube.Client):
    req = respx.post("https://localhost:9443/api/v1/namespaces/default/pods").respond(json={'metadata': {'name': 'xx'}})
    pod = client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'})))
    assert req.calls[0][0].read() == b'{"metadata": {"labels": {"l": "ok"}, "name": "xx"}}'
    assert pod.metadata.name == 'xx'

    req2 = respx.post("https://localhost:9443/api/v1/namespaces/other/pods").respond(json={'metadata': {'name': 'yy'}})
    pod = client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'})), namespace='other')
    assert pod.metadata.name == 'yy'
    assert req2.calls[0][0].read() == b'{"metadata": {"labels": {"l": "ok"}, "name": "xx"}}'

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
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'


@respx.mock
def test_replace_namespaced(client: lightkube.Client):
    req = respx.put("https://localhost:9443/api/v1/namespaces/default/pods/xy").respond(json={'metadata': {'name': 'xy'}})
    pod = client.replace(Pod(metadata=ObjectMeta(name="xy")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xy"}}'
    assert pod.metadata.name == 'xy'

    respx.put("https://localhost:9443/api/v1/namespaces/other/pods/xz").respond(json={'metadata': {'name': 'xz'}})
    pod = client.replace(Pod(metadata=ObjectMeta(name="xz")), namespace='other')
    assert pod.metadata.name == 'xz'

    # namespace inside object definition need to match with provided namespace parameter.
    with pytest.raises(ValueError):
        client.replace(Pod(metadata=ObjectMeta(name="xx", namespace='ns1')), namespace='ns2')


@respx.mock
def test_replace_global(client: lightkube.Client):
    req = respx.put("https://localhost:9443/api/v1/nodes/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = client.replace(Node(metadata=ObjectMeta(name="xx")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'

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
    lines = list(client.log('test', container="bla"))
    assert lines == result
