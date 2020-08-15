import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import json
import pytest
import httpx
import respx

import lightkube
from lightkube.config.config import KubeConfig
from lightkube.resources.core_v1 import Pod, Node, Binding
from lightkube.models.meta_v1 import ObjectMeta


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


@respx.mock
def test_get_namespaced(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx", content={'metadata': {'name': 'xx'}})
    pod = client.get(Pod, name="xx")
    assert pod.metadata.name == 'xx'

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods/xx", content={'metadata': {'name': 'xy'}})
    pod = client.get(Pod, name="xx", namespace="other")
    assert pod.metadata.name == 'xy'


@respx.mock
def test_get_global(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes/n1", content={'metadata': {'name': 'n1'}})
    pod = client.get(Node, name="n1")
    assert pod.metadata.name == 'n1'

    # GET doesn't support all namespaces
    with pytest.raises(ValueError):
        client.get(Pod, name="xx", namespace=lightkube.ALL)


@respx.mock
def test_list_namespaced(client: lightkube.Client):
    resp = {'items':[{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}]}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods", content=resp)
    pods = client.list(Pod)
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods?labelSelector=k%3Dv", content=resp)
    pods = client.list(Pod, namespace="other", labels={'k': 'v'})
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']


@respx.mock
def test_list_global(client: lightkube.Client):
    resp = {'items':[{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}]}
    respx.get("https://localhost:9443/api/v1/nodes", content=resp)
    nodes = client.list(Node)
    assert [node.metadata.name for node in nodes] == ['xx', 'yy']

    respx.get("https://localhost:9443/api/v1/pods?fieldSelector=k%3Dx", content=resp)
    pods = client.list(Pod, namespace=lightkube.ALL, fields={'k': 'x'})
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']

    # Binding doesn't support all namespaces
    with pytest.raises(ValueError):
        client.list(Binding, namespace=lightkube.ALL)


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
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx", content="Error", status_code=409)
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx", content={'message': 'got problems'},
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
    respx.get("https://localhost:9443/api/v1/nodes?watch=true", content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1", status_code=404)

    i = None
    with pytest.raises(httpx.HTTPError) as exi:
        for i, (op, node) in enumerate(client.watch(Node)):
            assert node.metadata.name == f'p{i}'
            assert op == 'ADDED'
    assert i == 9
    assert exi.value.response.status_code == 404


@respx.mock
def test_watch_version(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=2&watch=true", content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=1&watch=true", status_code=404)

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
    respx.get("https://localhost:9443/api/v1/nodes?watch=true", content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1", status_code=404)

    i = None
    for i, (op, node) in enumerate(client.watch(Node, on_error=lambda e: lightkube.WatchOnError.STOP)):
        assert node.metadata.name == f'p{i}'
        assert op == 'ADDED'
    assert i == 9


@respx.mock
def test_watch_stop_iter(client: lightkube.Client):
    respx.get("https://localhost:9443/api/v1/nodes?watch=true", content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1", status_code=404)

    i = None
    for i, (op, node) in enumerate(client.watch(Node, on_error=lambda e: lightkube.WatchOnError.RAISE)):
        break
    assert i == 0


@respx.mock
def test_patch_namespaced(client: lightkube.Client):
    req = respx.patch("https://localhost:9443/api/v1/namespaces/default/pods/xx", content={'metadata': {'name': 'xx'}})
    pod = client.patch(Pod, "xx", Pod(metadata=ObjectMeta(labels={'l': 'ok'})))
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/strategic-merge-patch+json"

    req = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xx", content={'metadata': {'name': 'xx'}})
    pod = client.patch(Pod, "xx", Pod(metadata=ObjectMeta(labels={'l': 'ok'})), namespace='other',
                       patch_type=lightkube.PatchType.MERGE)
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/merge-patch+json"


@respx.mock
def test_patch_global(client: lightkube.Client):
    req = respx.patch("https://localhost:9443/api/v1/nodes/xx", content={'metadata': {'name': 'xx'}})
    pod = client.patch(Node, "xx", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
                       patch_type=lightkube.PatchType.JSON)
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/json-patch+json"


@respx.mock
def test_create_namespaced(client: lightkube.Client):
    req = respx.post("https://localhost:9443/api/v1/namespaces/default/pods", content={'metadata': {'name': 'xx'}})
    pod = client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'})))
    assert req.calls[0][0].read() == b'{"metadata": {"labels": {"l": "ok"}, "name": "xx"}}'
    assert pod.metadata.name == 'xx'

    respx.post("https://localhost:9443/api/v1/namespaces/other/pods", content={'metadata': {'name': 'yy'}})
    pod = client.create(Pod(metadata=ObjectMeta(name="xx", labels={'l': 'ok'})), namespace='other')
    assert pod.metadata.name == 'yy'


@respx.mock
def test_create_global(client: lightkube.Client):
    req = respx.post("https://localhost:9443/api/v1/nodes", content={'metadata': {'name': 'xx'}})
    pod = client.create(Node(metadata=ObjectMeta(name="xx")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'


@respx.mock
def test_replace_namespaced(client: lightkube.Client):
    req = respx.put("https://localhost:9443/api/v1/namespaces/default/pods/xy", content={'metadata': {'name': 'xy'}})
    pod = client.replace(Pod(metadata=ObjectMeta(name="xy")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xy"}}'
    assert pod.metadata.name == 'xy'

    respx.put("https://localhost:9443/api/v1/namespaces/other/pods/xz", content={'metadata': {'name': 'xz'}})
    pod = client.replace(Pod(metadata=ObjectMeta(name="xz")), namespace='other')
    assert pod.metadata.name == 'xz'


@respx.mock
def test_replace_global(client: lightkube.Client):
    req = respx.put("https://localhost:9443/api/v1/nodes/xx", content={'metadata': {'name': 'xx'}})
    pod = client.replace(Node(metadata=ObjectMeta(name="xx")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'
