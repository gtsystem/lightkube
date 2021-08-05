from pathlib import Path
from unittest.mock import Mock
from lightkube.config import kubeconfig, client_adapter
from lightkube.config import models
from lightkube import ConfigError
import pytest
import httpx
import asyncio

BASEDIR = Path("tests")


def single_conf(cluster=None, user=None, fname=None):
    return kubeconfig.SingleConfig(
        context=models.Context(cluster="x"), context_name="x",
        cluster=cluster, user=user, fname=fname
    )


def test_verify_cluster_insecure():
    cfg = single_conf(cluster=models.Cluster(insecure=True))
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.abs_file)
    assert verify is False


def test_verify_cluster_secure():
    cfg = single_conf(cluster=models.Cluster())
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.abs_file)
    assert verify is True


def test_verify_cluster_ca(tmpdir):
    tmpdir = Path(tmpdir)
    cluster = models.Cluster(certificate_auth="ca.pem")
    cfg = single_conf(cluster=cluster, fname=tmpdir.joinpath("kubeconf"))
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.abs_file)
    assert verify == tmpdir.joinpath("ca.pem")

    # fname not provided
    cfg = single_conf(cluster=cluster)
    with pytest.raises(ConfigError):
        client_adapter.verify_cluster(cfg.cluster, cfg.abs_file)

    # cert path absolute
    cluster.certificate_auth = tmpdir.joinpath("ca.pem")
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.abs_file)
    assert verify == tmpdir.joinpath("ca.pem")


def test_verify_cluster_ca_data():
    cluster = models.Cluster(certificate_auth_data="dGVzdCBkZWNvZGluZw==")
    cfg = single_conf(cluster=cluster)
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.abs_file)
    assert Path(verify).read_text() == "test decoding"


def test_user_cert_missing():
    cfg = single_conf(user=models.User())
    assert client_adapter.user_cert(cfg.user, cfg.abs_file) is None


def test_user_cert(tmpdir):
    tmpdir = Path(tmpdir)
    cfg = single_conf(user=models.User(client_cert="a.crt", client_key="a.key"), fname=tmpdir.joinpath("conf"))
    certs = client_adapter.user_cert(cfg.user, cfg.abs_file)
    assert certs == (tmpdir.joinpath("a.crt"), tmpdir.joinpath("a.key"))


def test_user_cert_data():
    cfg = single_conf(user=models.User(client_cert_data="Y2VydA==", client_key_data="a2V5"))
    certs = client_adapter.user_cert(cfg.user, cfg.abs_file)
    assert Path(certs[0]).read_text() == "cert"
    assert Path(certs[1]).read_text() == "key"


def test_user_auth_missing():
    assert client_adapter.user_auth(None) is None


def test_user_auth_empty():
    assert client_adapter.user_auth(models.User()) is None


def test_user_auth_basic():
    auth = client_adapter.user_auth(models.User(username="user", password="psw"))
    assert isinstance(auth, httpx.BasicAuth)
    m = Mock(headers={})
    next(auth.auth_flow(m))
    assert m.headers["Authorization"] == "Basic dXNlcjpwc3c="


def test_user_auth_bearer():
    auth = client_adapter.user_auth(models.User(token="abcd"))
    assert isinstance(auth, client_adapter.BearerAuth)
    m = Mock(headers={})
    next(auth.auth_flow(m))
    assert m.headers["Authorization"] == "Bearer abcd"


def test_user_auth_provider():
    """Auth provider not supported"""
    with pytest.raises(ConfigError):
        client_adapter.user_auth(models.User(auth_provider={'x': 1}))


def test_user_auth_exec_sync():
    auth_script = str(Path(__file__).parent.joinpath('data', 'auth_script.sh'))
    auth = client_adapter.user_auth(models.User(exec=models.UserExec(
        apiVersion="client.authentication.k8s.io/v1beta1",
        command=auth_script,
    )))
    assert isinstance(auth, client_adapter.ExecAuth)
    m = Mock(headers={})
    next(auth.sync_auth_flow(m))
    assert m.headers["Authorization"] == "Bearer my-bearer-token"

    # call again should cache
    m = Mock(headers={})
    flow = auth.sync_auth_flow(m)
    next(flow)
    assert m.headers["Authorization"] == "Bearer my-bearer-token"
    m.headers["Authorization"] = None

    # we pretend the cache is old
    flow.send(httpx.Response(status_code=401, request=m))
    assert m.headers["Authorization"] == "Bearer my-bearer-token"


def test_user_auth_exec_sync_with_args():
    auth = client_adapter.user_auth(models.User(exec=models.UserExec(
        apiVersion="client.authentication.k8s.io/v1beta1",
        args=['{"apiVersion":"client.authentication.k8s.io/v1beta1",'
              '"kind":"ExecCredential","status":{"token":"my-bearer-token"}}'],
        command='echo',
    )))
    assert isinstance(auth, client_adapter.ExecAuth)
    m = Mock(headers={})
    next(auth.sync_auth_flow(m))
    assert m.headers["Authorization"] == "Bearer my-bearer-token"


def test_user_auth_exec_sync_fail():
    auth = client_adapter.user_auth(models.User(exec=models.UserExec(
        apiVersion="client.authentication.k8s.io/v1beta1",
        command="cp"
    )))
    with pytest.raises(ConfigError, match="cp"):
        next(auth.sync_auth_flow(Mock(headers={})))


@pytest.mark.asyncio
async def test_user_auth_exec_async():
    auth_script = str(Path(__file__).parent.joinpath('data', 'auth_script.sh'))
    auth = client_adapter.user_auth(models.User(exec=models.UserExec(
        apiVersion="client.authentication.k8s.io/v1beta1",
        command=auth_script,
    )))

    assert isinstance(auth, client_adapter.ExecAuth)
    m = Mock(headers={})
    await auth.async_auth_flow(m).__anext__()
    assert m.headers["Authorization"] == "Bearer my-bearer-token"

    # call again should cache
    m = Mock(headers={})
    flow = auth.async_auth_flow(m)
    await flow.__anext__()
    assert m.headers["Authorization"] == "Bearer my-bearer-token"
    m.headers["Authorization"] = None

    # we pretend the cache is old
    await flow.asend(httpx.Response(status_code=401, request=m))
    assert m.headers["Authorization"] == "Bearer my-bearer-token"
    with pytest.raises(StopAsyncIteration):
        await flow.__anext__()


@pytest.mark.asyncio
async def test_user_auth_exec_async_fail():
    auth = client_adapter.user_auth(models.User(exec=models.UserExec(
        apiVersion="client.authentication.k8s.io/v1beta1",
        command="cp"
    )))
    with pytest.raises(ConfigError, match="cp"):
        await auth.async_auth_flow(Mock(headers={})).__anext__()
