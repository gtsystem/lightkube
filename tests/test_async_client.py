import unittest.mock
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import pytest
import httpx
import respx

import lightkube
from lightkube.config.kubeconfig import KubeConfig
from lightkube.resources.core_v1 import Pod, Node, Binding
from lightkube.generic_resource import create_global_resource
from lightkube.models.meta_v1 import ObjectMeta
from lightkube import types

from .test_client import make_wait_custom, make_wait_deleted, make_wait_failed, make_wait_success, make_watch_list

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
    return lightkube.AsyncClient(config=config)


def test_namespace(client: lightkube.Client, kubeconfig_ns):
    assert client.namespace == 'default'

    config = KubeConfig.from_file(str(kubeconfig_ns))
    client = lightkube.AsyncClient(config=config)
    assert client.namespace == 'ns1'


@unittest.mock.patch('httpx.AsyncClient')
@unittest.mock.patch('lightkube.config.client_adapter.user_auth')
def test_client_httpx_attributes(user_auth, httpx_async_client, kubeconfig):
    config = KubeConfig.from_file(kubeconfig)
    single_conf = config.get()
    lightkube.AsyncClient(config=single_conf, trust_env=False)
    httpx_async_client.assert_called_once_with(
        timeout=None,
        base_url=single_conf.cluster.server,
        verify=True,
        cert=None,
        auth=user_auth.return_value,
        trust_env=False
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_namespaced(client: lightkube.AsyncClient):
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = await client.get(Pod, name="xx")
    assert pod.metadata.name == 'xx'

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods/xx").respond(json={'metadata': {'name': 'xy'}})
    pod = await client.get(Pod, name="xx", namespace="other")
    assert pod.metadata.name == 'xy'
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_list_global(client: lightkube.AsyncClient):
    resp = {'items': [{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}]}
    respx.get("https://localhost:9443/api/v1/nodes").respond(json=resp)
    nodes = client.list(Node)
    assert [node.metadata.name async for node in nodes] == ['xx', 'yy']

    respx.get("https://localhost:9443/api/v1/pods?fieldSelector=k%3Dx").respond(json=resp)
    pods = client.list(Pod, namespace=lightkube.ALL_NS, fields={'k': 'x'})
    assert [pod.metadata.name async for pod in pods] == ['xx', 'yy']

    # Binding doesn't support all namespaces
    with pytest.raises(ValueError):
        client.list(Binding, namespace=lightkube.ALL_NS)
    await client.close()

@respx.mock
@pytest.mark.asyncio
async def test_list_chunk_size(client: lightkube.AsyncClient):
    resp = {'items': [{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}], 'metadata': {'continue': 'yes'}}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods?limit=3").respond(json=resp)
    resp = {'items': [{'metadata': {'name': 'zz'}}]}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods?limit=3&continue=yes").respond(json=resp)
    pods = client.list(Pod, chunk_size=3)
    assert [pod.metadata.name async for pod in pods] == ['xx', 'yy', 'zz']
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_delete_global(client: lightkube.AsyncClient):
    respx.delete("https://localhost:9443/api/v1/nodes/xx")
    await client.delete(Node, name="xx")
    await client.close()

@respx.mock
@pytest.mark.asyncio
async def test_deletecollection_global(client: lightkube.AsyncClient):
    respx.delete("https://localhost:9443/api/v1/nodes")
    await client.deletecollection(Node)
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_watch(client: lightkube.AsyncClient):
    respx.get("https://localhost:9443/api/v1/nodes?watch=true").respond(content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1").respond(status_code=404)

    i = -1
    with pytest.raises(httpx.HTTPError) as exi:
        async for (op, node) in client.watch(Node):
            i += 1
            assert node.metadata.name == f'p{i}'
            assert op == 'ADDED'

    assert i == 9
    assert exi.value.response.status_code == 404
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_watch_version(client: lightkube.AsyncClient):
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=2&watch=true").respond(content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=1&watch=true").respond(status_code=404)

    # testing starting from specific resource version
    i = -1
    with pytest.raises(httpx.HTTPError) as exi:
        async for (op, node) in client.watch(Node, resource_version="2"):
            i += 1
            assert node.metadata.name == f'p{i}'
            assert op == 'ADDED'
    assert i == 9
    assert exi.value.response.status_code == 404
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_wait_success(client: lightkube.AsyncClient):
    base_url = "https://localhost:9443/api/v1/nodes?fieldSelector=metadata.name%3Dtest-node&watch=true"

    respx.get(base_url).respond(content=make_wait_success())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_success())

    node = await client.wait(Node, "test-node", for_conditions=["TestCondition"])

    assert node.to_dict()["metadata"]["name"] == "test-node"

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_wait_deleted(client: lightkube.AsyncClient):
    base_url = "https://localhost:9443/api/v1/nodes?fieldSelector=metadata.name%3Dtest-node&watch=true"

    respx.get(base_url).respond(content=make_wait_deleted())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_deleted())

    message = "nodes/test-node was unexpectedly deleted"
    with pytest.raises(lightkube.core.exceptions.ObjectDeleted, match=message):
        await client.wait(Node, "test-node", for_conditions=["TestCondition"])

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_wait_failed(client: lightkube.AsyncClient):
    base_url = "https://localhost:9443/api/v1/nodes?fieldSelector=metadata.name%3Dtest-node&watch=true"

    respx.get(base_url).respond(content=make_wait_failed())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_failed())

    message = r"nodes/test-node has failure condition\(s\): TestCondition"
    with pytest.raises(lightkube.core.exceptions.ConditionError, match=message):
        await client.wait(Node, "test-node", for_conditions=[], raise_for_conditions=["TestCondition"])

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_wait_custom(client: lightkube.AsyncClient):
    base_url = "https://localhost:9443/apis/custom.org/v1/customs?fieldSelector=metadata.name%3Dcustom-resource&watch=true"

    Custom = create_global_resource(
        group="custom.org", version="v1", kind="Custom", plural="customs"
    )
    respx.get(base_url).respond(content=make_wait_custom())
    respx.get(base_url + "&resourceVersion=1").respond(content=make_wait_custom())

    await client.wait(Custom, "custom-resource", for_conditions=["TestCondition"])

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_patch_global(client: lightkube.AsyncClient):
    req = respx.patch("https://localhost:9443/api/v1/nodes/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = await client.patch(Node, "xx", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
                             patch_type=types.PatchType.JSON)
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/json-patch+json"

    # PatchType.APPLY + force
    req = respx.patch("https://localhost:9443/api/v1/nodes/xy?fieldManager=test&force=true").respond(
        json={'metadata': {'name': 'xy'}})
    node = await client.patch(Node, "xy", Pod(metadata=ObjectMeta(labels={'l': 'ok'})),
                              patch_type=types.PatchType.APPLY, field_manager='test', force=True)
    assert node.metadata.name == 'xy'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_create_global(client: lightkube.AsyncClient):
    req = respx.post("https://localhost:9443/api/v1/nodes").respond(json={'metadata': {'name': 'xx'}})
    pod = await client.create(Node(metadata=ObjectMeta(name="xx")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_replace_global(client: lightkube.AsyncClient):
    req = respx.put("https://localhost:9443/api/v1/nodes/xx").respond(json={'metadata': {'name': 'xx'}})
    pod = await client.replace(Node(metadata=ObjectMeta(name="xx")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'
    await client.close()


async def alist(aiter):
    return [l async for l in aiter]


@respx.mock
@pytest.mark.asyncio
async def test_pod_log(client: lightkube.AsyncClient):
    result = ['line1\n', 'line2\n', 'line3\n']
    content = "".join(result)

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log").respond(content=content)
    lines = await alist(client.log('test'))
    assert lines == result

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log?since=30&timestamps=true").respond(
        content=content)
    lines = await alist(client.log('test', since=30, timestamps=True))
    assert lines == result

    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/test/log?container=bla").respond(
        content=content)
    lines = await alist(client.log('test', container="bla"))
    assert lines == result
    await client.close()

@respx.mock
@pytest.mark.asyncio
async def test_apply_namespaced(client: lightkube.AsyncClient):
    req = respx.patch("https://localhost:9443/api/v1/namespaces/default/pods/xy?fieldManager=test").respond(
        json={'metadata': {'name': 'xy'}})
    pod = await client.apply(Pod(metadata=ObjectMeta(name='xy')), field_manager='test')
    assert pod.metadata.name == 'xy'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # custom namespace, force
    req = respx.patch("https://localhost:9443/api/v1/namespaces/other/pods/xz?fieldManager=a&force=true").respond(
        json={'metadata': {'name': 'xz'}})
    pod = await client.apply(Pod(metadata=ObjectMeta(name='xz', namespace='other')), field_manager='a', force=True)
    assert pod.metadata.name == 'xz'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # sub-resource
    req = respx.patch("https://localhost:9443/api/v1/namespaces/default/pods/xx/status?fieldManager=a").respond(
        json={'metadata': {'name': 'xx'}})
    pod = await client.apply(Pod.Status(), name='xx', field_manager='a')
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_apply_global(client: lightkube.AsyncClient):
    req = respx.patch("https://localhost:9443/api/v1/nodes/xy?fieldManager=test").respond(
        json={'metadata': {'name': 'xy'}})
    node = await client.apply(Node(metadata=ObjectMeta(name='xy')), field_manager='test')
    assert node.metadata.name == 'xy'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"

    # sub-resource + force
    req = respx.patch("https://localhost:9443/api/v1/nodes/xx/status?fieldManager=a&force=true").respond(
        json={'metadata': {'name': 'xx'}})
    node = await client.apply(Node.Status(), name='xx', field_manager='a', force=True)
    assert node.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/apply-patch+yaml"
    await client.close()
