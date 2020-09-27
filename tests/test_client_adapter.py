from pathlib import Path
from lightkube.config import config, client_adapter
from lightkube import ConfigError
import pytest

BASEDIR = Path("tests")


def test_exec_with_args():
    cfg = config.KubeConfig.from_file(BASEDIR / "test_config_exec.yaml")
    kwargs = {}
    client_adapter._setup_request_auth(cfg, kwargs)
    assert kwargs == {'headers': {'Authorization': 'Bearer my-bearer-token'}}


def test_exec_with_envs():
    cfg = config.KubeConfig.from_file(BASEDIR / "test_config_exec.yaml", current_context='ctx2')
    kwargs = {}
    client_adapter._setup_request_auth(cfg, kwargs)
    assert kwargs == {'headers': {'Authorization': 'Bearer my-bearer-token'}}


def test_exec_wrong_version():
    cfg = config.KubeConfig.from_file(BASEDIR / "test_config_exec.yaml")
    cfg.user["exec"]["apiVersion"] = "client.authentication.k8s.io/v1beta5"
    with pytest.raises(ConfigError):
        client_adapter._setup_request_auth(cfg, {})


def test_username():
    cfg = config.KubeConfig.from_file(BASEDIR / "test_config_user_password.yaml")
    kwargs = {}
    client_adapter._setup_request_auth(cfg, kwargs)
    assert kwargs == {'auth': ('bla', 'bla123')}
