import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import pytest
import httpx
import respx

import lightkube
from lightkube.config.kubeconfig import KubeConfig
from lightkube.resources.core_v1 import Pod, Node, Binding
from lightkube.models.meta_v1 import ObjectMeta
from lightkube import types

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


@respx.mock
@pytest.mark.asyncio
async def test_get_namespaced(client: lightkube.AsyncClient):
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods/xx", content={'metadata': {'name': 'xx'}})
    pod = await client.get(Pod, name="xx")
    assert pod.metadata.name == 'xx'

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods/xx", content={'metadata': {'name': 'xy'}})
    pod = await client.get(Pod, name="xx", namespace="other")
    assert pod.metadata.name == 'xy'
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_list_global(client: lightkube.AsyncClient):
    resp = {'items': [{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}]}
    respx.get("https://localhost:9443/api/v1/nodes", content=resp)
    nodes = client.list(Node)
    assert [node.metadata.name async for node in nodes] == ['xx', 'yy']

    respx.get("https://localhost:9443/api/v1/pods?fieldSelector=k%3Dx", content=resp)
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
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods?limit=3", content=resp)
    resp = {'items': [{'metadata': {'name': 'zz'}}]}
    respx.get("https://localhost:9443/api/v1/namespaces/default/pods?limit=3&continue=yes", content=resp)
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

from tests.test_client import make_watch_list


@respx.mock
@pytest.mark.asyncio
async def test_watch(client: lightkube.AsyncClient):
    respx.get("https://localhost:9443/api/v1/nodes?watch=true", content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?watch=true&resourceVersion=1", status_code=404)

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
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=2&watch=true", content=make_watch_list())
    respx.get("https://localhost:9443/api/v1/nodes?resourceVersion=1&watch=true", status_code=404)

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
async def test_patch_global(client: lightkube.AsyncClient):
    req = respx.patch("https://localhost:9443/api/v1/nodes/xx", content={'metadata': {'name': 'xx'}})
    pod = await client.patch(Node, "xx", [{"op": "add", "path": "/metadata/labels/x", "value": "y"}],
                       patch_type=types.PatchType.JSON)
    assert pod.metadata.name == 'xx'
    assert req.calls[0][0].headers['Content-Type'] == "application/json-patch+json"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_create_global(client: lightkube.AsyncClient):
    req = respx.post("https://localhost:9443/api/v1/nodes", content={'metadata': {'name': 'xx'}})
    pod = await client.create(Node(metadata=ObjectMeta(name="xx")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_replace_global(client: lightkube.AsyncClient):
    req = respx.put("https://localhost:9443/api/v1/nodes/xx", content={'metadata': {'name': 'xx'}})
    pod = await client.replace(Node(metadata=ObjectMeta(name="xx")))
    assert req.calls[0][0].read() == b'{"metadata": {"name": "xx"}}'
    assert pod.metadata.name == 'xx'
    await client.close()
