import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lightkube.config import kubeconfig
from lightkube.core import exceptions


def test_from_server():
    cfg = kubeconfig.KubeConfig.from_server("http://testserver.com").get()
    assert cfg.context_name == "default"
    assert cfg.namespace == "default"
    assert cfg.cluster.server == "http://testserver.com"
    assert cfg.user is None

    cfg = kubeconfig.KubeConfig.from_server("http://testserver.com", namespace="ns").get()
    assert cfg.context_name == "default"
    assert cfg.namespace == "ns"


@pytest.fixture()
def cfg():
    fname = Path("tests").joinpath("test_config.yaml")
    return kubeconfig.KubeConfig.from_file(fname)


def test_from_file(cfg):
    c = cfg.get()
    assert c.context_name == "ctx11"
    assert c.user.username == "u1"
    assert c.user.password == "p1"
    assert c.cluster.server == "server1"
    assert c.context.user == "user1"
    assert c.namespace == kubeconfig.DEFAULT_NAMESPACE

    c = cfg.get(context_name="ctx12")
    assert c.context_name == "ctx12"
    assert c.user.token == "ABC"
    assert c.cluster.server == "server1"
    assert c.context.user == "user2"
    assert c.namespace == kubeconfig.DEFAULT_NAMESPACE

    c = cfg.get(context_name="ctx21")
    assert c.context_name == "ctx21"
    assert c.user.username == "u1"
    assert c.cluster.server == "server2"
    assert c.context.cluster == "cl2"
    assert c.namespace == "ns21"


def test_from_file_miss_config(cfg):
    # non existing context raise an exception
    with pytest.raises(exceptions.ConfigError):
        assert cfg.get(context_name="ctx22")

    # if default context is missing, raise an exception
    cfg.current_context = None
    with pytest.raises(exceptions.ConfigError):
        assert cfg.get()

    # default context is missing, but a default is provided
    c = cfg.get(default=kubeconfig.PROXY_CONF)
    assert c is kubeconfig.PROXY_CONF


def test_from_dict():
    cfg = kubeconfig.KubeConfig.from_dict(
        {
            "clusters": [{"name": "cl1", "cluster": {"server": "a"}}],
            "contexts": [{"name": "a", "context": {"cluster": "cl1", "namespace": "ns"}}],
        }
    )
    assert cfg.current_context is None
    assert cfg.clusters["cl1"].server == "a"
    assert cfg.contexts["a"].namespace == "ns"

    c = cfg.get("a")
    assert c.namespace == "ns"
    assert c.cluster.server == "a"


@pytest.fixture
def service_account(tmpdir):
    tmpdir = Path(tmpdir)
    tmpdir.joinpath("namespace").write_text("my-namespace")
    tmpdir.joinpath("token").write_text("ABCD")
    tmpdir.joinpath("ca.crt").write_text("...bla...")

    os.environ["KUBERNETES_SERVICE_HOST"] = "k8s.local"
    os.environ["KUBERNETES_SERVICE_PORT"] = "9443"
    return tmpdir


def test_from_service_account(service_account):
    cfg = kubeconfig.KubeConfig.from_service_account(service_account)
    c = cfg.get()
    assert c.namespace == "my-namespace"
    assert c.user.token == "ABCD"
    assert c.cluster.server == "https://k8s.local:9443"


def test_from_service_account_not_found(tmpdir):
    with pytest.raises(exceptions.ConfigError):
        kubeconfig.KubeConfig.from_service_account(tmpdir)


def test_from_file_not_found(tmpdir):
    with pytest.raises(exceptions.ConfigError):
        kubeconfig.KubeConfig.from_file(Path(tmpdir).joinpath("bla"))


def test_from_env(service_account):
    cfg = kubeconfig.KubeConfig.from_env(service_account)
    assert cfg.get().user.token == "ABCD"

    with patch("lightkube.config.kubeconfig.os.environ") as environ:
        environ.get.return_value = str(Path("tests").joinpath("test_config.yaml"))
        cfg = kubeconfig.KubeConfig.from_env(service_account.joinpath("xyz"))
        assert cfg.get().context_name == "ctx11"
        environ.get.assert_called_with("KUBECONFIG", kubeconfig.DEFAULT_KUBECONFIG)

    with patch("lightkube.config.kubeconfig.os.environ") as environ:
        environ.get.return_value = str(Path("tests").joinpath("test_config.yaml"))
        cfg = kubeconfig.KubeConfig.from_env(service_account.joinpath("xyz"), default_config="/tmp/bla")
        assert cfg.get().context_name == "ctx11"
        environ.get.assert_called_with("KUBECONFIG", "/tmp/bla")
