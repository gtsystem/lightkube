import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import pytest
import lightkube
from lightkube.config.config import KubeConfig
import respx
from lightkube.resources.core_v1 import Pod, Node, Binding


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

    respx.get("https://localhost:9443/api/v1/namespaces/other/pods", content=resp)
    pods = client.list(Pod, namespace="other")
    assert [pod.metadata.name for pod in pods] == ['xx', 'yy']


@respx.mock
def test_list_global(client: lightkube.Client):
    resp = {'items':[{'metadata': {'name': 'xx'}}, {'metadata': {'name': 'yy'}}]}
    respx.get("https://localhost:9443/api/v1/nodes", content=resp)
    nodes = client.list(Node)
    assert [node.metadata.name for node in nodes] == ['xx', 'yy']

    respx.get("https://localhost:9443/api/v1/pods", content=resp)
    pods = client.list(Pod, namespace=lightkube.ALL)
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
