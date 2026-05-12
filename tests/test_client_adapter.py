import base64
import shutil
import ssl
import unittest
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from lightkube import ConfigError
from lightkube.config import client_adapter, kubeconfig, models

BASEDIR = Path("tests")


def single_conf(cluster=None, user=None, fname=None):
    return kubeconfig.SingleConfig(
        context=models.Context(cluster="x"), context_name="x", cluster=cluster, user=user, fname=fname
    )


def test_verify_cluster_insecure():
    cfg = single_conf(cluster=models.Cluster(insecure=True), user=models.User())
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.user, cfg.abs_file)
    assert verify.verify_mode is ssl.CERT_NONE
    assert not verify.check_hostname


def test_verify_cluster_secure():
    cfg = single_conf(cluster=models.Cluster(), user=models.User())
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.user, cfg.abs_file)
    assert verify.verify_mode is ssl.CERT_REQUIRED


def get_issuer_mata(data: dict):
    return {d[0][0]: d[0][1] for d in data["issuer"]}


def test_verify_cluster_ca_path(tmpdir):
    tmpdir = Path(tmpdir)
    data_dir = Path(__file__).parent.joinpath("data")
    shutil.copy(data_dir.joinpath("clientreq.pem"), tmpdir.joinpath("clientreq.pem"))
    cluster = models.Cluster(certificate_auth="clientreq.pem")
    cfg = single_conf(cluster=cluster, user=models.User(), fname=tmpdir.joinpath("kubeconf"))
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.user, cfg.abs_file)
    assert get_issuer_mata(verify.get_ca_certs()[0])["organizationName"] == "Example"

    # fname not provided
    cfg = single_conf(cluster=models.Cluster(certificate_auth="clientreq.pem"), user=models.User())
    with pytest.raises(ConfigError):
        client_adapter.verify_cluster(cfg.cluster, cfg.user, cfg.abs_file)

    # cert path absolute
    cluster = models.Cluster(certificate_auth=str(data_dir.joinpath("clientreq.pem")))
    verify = client_adapter.verify_cluster(cluster, cfg.user, cfg.abs_file)
    assert get_issuer_mata(verify.get_ca_certs()[0])["organizationName"] == "Example"


def test_verify_cluster_ca_data():
    data_dir = Path(__file__).parent.joinpath("data")
    cert_data = base64.b64encode(data_dir.joinpath("clientreq.pem").read_bytes()).decode("utf8")

    cluster = models.Cluster(certificate_auth_data=cert_data)
    cfg = single_conf(cluster=cluster, user=models.User())
    verify = client_adapter.verify_cluster(cfg.cluster, cfg.user, cfg.abs_file)
    assert get_issuer_mata(verify.get_ca_certs()[0])["organizationName"] == "Example"


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


@unittest.mock.patch("ssl.create_default_context")
def test_verify_cluster_ca_and_cert(create_default_context):
    data_dir = Path(__file__).parent.joinpath("data")
    cluster = models.Cluster(certificate_auth=str(data_dir.joinpath("clientreq.pem")))
    cfg = single_conf(
        cluster=cluster,
        user=models.User(
            client_cert=str(data_dir.joinpath("clientreq.pem")), client_key=str(data_dir.joinpath("clientkey.pem"))
        ),
    )
    verify = client_adapter.verify_cluster(cluster, cfg.user, cfg.abs_file)
    assert verify is create_default_context.return_value
    create_default_context.assert_called_once_with(cafile=str(data_dir.joinpath("clientreq.pem")))
    create_default_context.return_value.load_cert_chain.assert_called_once_with(
        str(data_dir.joinpath("clientreq.pem")), str(data_dir.joinpath("clientkey.pem"))
    )


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


def test_user_auth_bearer_token_file(tmp_path):
    """BearerTokenFileAuth is used when token_file is set"""
    token_file = tmp_path / "token"
    token_file.write_text("my-sa-token")
    auth = client_adapter.user_auth(models.User(token_file=str(token_file)))
    assert isinstance(auth, client_adapter.BearerTokenFileAuth)
    m = Mock(headers={})
    next(auth.auth_flow(m))
    assert m.headers["Authorization"] == "Bearer my-sa-token"


def test_user_auth_bearer_token_file_priority(tmp_path):
    """token_file takes priority over static token"""
    token_file = tmp_path / "token"
    token_file.write_text("file-token")
    auth = client_adapter.user_auth(models.User(token="static-token", token_file=str(token_file)))
    assert isinstance(auth, client_adapter.BearerTokenFileAuth)
    m = Mock(headers={})
    next(auth.auth_flow(m))
    assert m.headers["Authorization"] == "Bearer file-token"


def test_bearer_token_file_auth_refresh(tmp_path):
    """Token is re-read from file on 401"""
    token_file = tmp_path / "token"
    token_file.write_text("old-token")

    auth = client_adapter.BearerTokenFileAuth(str(token_file))
    m = Mock(headers={})

    # First request uses the initial token
    flow = auth.auth_flow(m)
    next(flow)
    assert m.headers["Authorization"] == "Bearer old-token"

    # Simulate token rotation
    token_file.write_text("new-token")

    # Server returns 401
    m.headers["Authorization"] = None
    flow.send(httpx.Response(status_code=401, request=m))
    assert m.headers["Authorization"] == "Bearer new-token"


def test_bearer_token_file_auth_no_refresh_on_success(tmp_path):
    """Token is NOT re-read on non-401 responses"""
    token_file = tmp_path / "token"
    token_file.write_text("my-token")

    auth = client_adapter.BearerTokenFileAuth(str(token_file))
    m = Mock(headers={})

    flow = auth.auth_flow(m)
    next(flow)
    assert m.headers["Authorization"] == "Bearer my-token"

    # Token changes on disk, but server returned 200
    token_file.write_text("new-token")
    with pytest.raises(StopIteration):
        flow.send(httpx.Response(status_code=200, request=m))

    # Cached token is still used on next request
    m2 = Mock(headers={})
    flow2 = auth.auth_flow(m2)
    next(flow2)
    assert m2.headers["Authorization"] == "Bearer my-token"


def test_bearer_token_file_auth_caching(tmp_path):
    """Token is cached between requests"""
    token_file = tmp_path / "token"
    token_file.write_text("cached-token")

    auth = client_adapter.BearerTokenFileAuth(str(token_file))

    # First request reads from file
    m1 = Mock(headers={})
    flow1 = auth.auth_flow(m1)
    next(flow1)
    assert m1.headers["Authorization"] == "Bearer cached-token"
    with pytest.raises(StopIteration):
        flow1.send(httpx.Response(status_code=200, request=m1))

    # Token changes but cache is used
    token_file.write_text("different-token")

    m2 = Mock(headers={})
    flow2 = auth.auth_flow(m2)
    next(flow2)
    assert m2.headers["Authorization"] == "Bearer cached-token"


def test_bearer_token_file_auth_file_not_found(tmp_path):
    """ConfigError raised if token file doesn't exist"""
    auth = client_adapter.BearerTokenFileAuth(str(tmp_path / "nonexistent"))
    with pytest.raises(ConfigError, match="not found"):
        next(auth.auth_flow(Mock(headers={})))


@pytest.mark.asyncio
async def test_bearer_token_file_auth_async_refresh(tmp_path):
    """Token refresh works through the inherited async_auth_flow delegation"""
    token_file = tmp_path / "token"
    token_file.write_text("old-token")

    auth = client_adapter.BearerTokenFileAuth(str(token_file))
    m = Mock(headers={})

    flow = auth.async_auth_flow(m)
    await flow.__anext__()
    assert m.headers["Authorization"] == "Bearer old-token"

    # Simulate token rotation
    token_file.write_text("new-token")

    # Server returns 401
    m.headers["Authorization"] = None
    await flow.asend(httpx.Response(status_code=401, request=m))
    assert m.headers["Authorization"] == "Bearer new-token"

    with pytest.raises(StopAsyncIteration):
        await flow.__anext__()


@pytest.mark.asyncio
async def test_bearer_token_file_auth_async_no_refresh_on_success(tmp_path):
    """No refresh on success through inherited async_auth_flow delegation"""
    token_file = tmp_path / "token"
    token_file.write_text("my-token")

    auth = client_adapter.BearerTokenFileAuth(str(token_file))
    m = Mock(headers={})

    flow = auth.async_auth_flow(m)
    await flow.__anext__()
    assert m.headers["Authorization"] == "Bearer my-token"

    with pytest.raises(StopAsyncIteration):
        await flow.asend(httpx.Response(status_code=200, request=m))


def test_user_auth_provider():
    """Auth provider not supported"""
    with pytest.raises(ConfigError):
        client_adapter.user_auth(models.User(auth_provider={"x": 1}))


def test_user_auth_exec_sync():
    auth_script = str(Path(__file__).parent.joinpath("data", "auth_script.sh"))
    auth = client_adapter.user_auth(
        models.User(
            exec=models.UserExec(
                apiVersion="client.authentication.k8s.io/v1beta1",
                command=auth_script,
            )
        )
    )
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
    auth = client_adapter.user_auth(
        models.User(
            exec=models.UserExec(
                apiVersion="client.authentication.k8s.io/v1beta1",
                args=[
                    '{"apiVersion":"client.authentication.k8s.io/v1beta1",'
                    '"kind":"ExecCredential","status":{"token":"my-bearer-token"}}'
                ],
                command="echo",
            )
        )
    )
    assert isinstance(auth, client_adapter.ExecAuth)
    m = Mock(headers={})
    next(auth.sync_auth_flow(m))
    assert m.headers["Authorization"] == "Bearer my-bearer-token"


def test_user_auth_exec_sync_fail():
    auth = client_adapter.user_auth(
        models.User(exec=models.UserExec(apiVersion="client.authentication.k8s.io/v1beta1", command="cp"))
    )
    with pytest.raises(ConfigError, match="cp"):
        next(auth.sync_auth_flow(Mock(headers={})))


@pytest.mark.asyncio
async def test_user_auth_exec_async():
    auth_script = str(Path(__file__).parent.joinpath("data", "auth_script.sh"))
    auth = client_adapter.user_auth(
        models.User(
            exec=models.UserExec(
                apiVersion="client.authentication.k8s.io/v1beta1",
                command=auth_script,
            )
        )
    )

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
    auth = client_adapter.user_auth(
        models.User(exec=models.UserExec(apiVersion="client.authentication.k8s.io/v1beta1", command="cp"))
    )
    with pytest.raises(ConfigError, match="cp"):
        await auth.async_auth_flow(Mock(headers={})).__anext__()
