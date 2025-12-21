import asyncio.subprocess
import json
import os
import ssl
import subprocess
from dataclasses import asdict, dataclass, field
from typing import AsyncGenerator, Callable, Dict, Generator, List, Mapping, Optional, Sequence, Tuple, overload

import httpx

from ..core.exceptions import ConfigError
from .kubeconfig import SingleConfig, StrOrPath
from .models import Cluster, FileStr, User, UserExec


@dataclass
class ConnectionParams:
    """All connection parameters used by Client and AsyncClient"""

    timeout: Optional[httpx.Timeout] = field(default_factory=lambda: httpx.Timeout(10))
    trust_env: bool = True
    transport: Optional[httpx.BaseTransport] = None
    proxy: Optional[str] = None
    http2: bool = False

    def httpx_params(self, config: SingleConfig) -> dict:
        base_url = config.cluster.server
        assert config.user, "Missing user"
        verify = verify_cluster(config.cluster, config.user, config.abs_file, trust_env=self.trust_env)
        auth = user_auth(config.user)
        return dict(base_url=base_url, verify=verify, auth=auth, **asdict(self))


def Client(config: SingleConfig, conn_parameters: ConnectionParams) -> httpx.Client:
    return httpx.Client(**conn_parameters.httpx_params(config))


def AsyncClient(config: SingleConfig, conn_parameters: ConnectionParams) -> httpx.AsyncClient:
    return httpx.AsyncClient(**conn_parameters.httpx_params(config))


class BearerAuth(httpx.Auth):
    def __init__(self, token: str) -> None:
        self._bearer = f"Bearer {token}"

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = self._bearer
        yield request


async def async_check_output(command: Sequence[str], env: Mapping[str, str]) -> bytes:
    PIPE = asyncio.subprocess.PIPE
    proc = await asyncio.create_subprocess_exec(*command, env=env, stdin=None, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise ConfigError(f"Exec {command[0]} returned {proc.returncode}: {stderr.decode()}")
    return stdout


def sync_check_output(command: Sequence[str], env: Mapping[str, str]) -> bytes:
    proc = subprocess.Popen(command, env=env, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise ConfigError(f"Exec {command[0]} returned {proc.returncode}: {stderr.decode()}")
    return stdout


class ExecAuth(httpx.Auth):
    # The param name `exec` shadows the Python builtin, but changing the kwarg name would potentially break users code
    def __init__(self, exec: UserExec) -> None:  # noqa: A002
        self._exec = exec
        self._last_bearer: Optional[str] = None

    def _prepare(self) -> Tuple[List[str], Dict[str, str]]:
        _exec = self._exec
        if _exec.apiVersion not in (
            "client.authentication.k8s.io/v1alpha1",
            "client.authentication.k8s.io/v1beta1",
        ):
            raise ConfigError(f"auth exec api version {_exec.apiVersion} not implemented")
        cmd_env_vars = dict(os.environ)
        if _exec.env:
            cmd_env_vars.update((var.name, var.value) for var in _exec.env)
        # TODO: add support for passing KUBERNETES_EXEC_INFO env var
        # https://github.com/kubernetes/community/blob/master/contributors/design-proposals/auth/kubectl-exec-plugins.md
        args = _exec.args if _exec.args else []
        return [_exec.command, *args], cmd_env_vars

    def sync_auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        if self._last_bearer:
            request.headers["Authorization"] = self._last_bearer
            response = yield request
            if response.status_code != 401:
                return

        command, env = self._prepare()
        output = sync_check_output(command, env=env)
        token = json.loads(output)["status"]["token"]
        request.headers["Authorization"] = self._last_bearer = f"Bearer {token}"
        yield request

    async def async_auth_flow(self, request: httpx.Request) -> AsyncGenerator[httpx.Request, httpx.Response]:
        if self._last_bearer:
            request.headers["Authorization"] = self._last_bearer
            response = yield request
            if response.status_code != 401:
                return

        command, env = self._prepare()
        output = await async_check_output(command, env=env)
        token = json.loads(output)["status"]["token"]
        request.headers["Authorization"] = self._last_bearer = f"Bearer {token}"
        yield request


@overload
def user_auth(user: User) -> Optional[httpx.Auth]: ...


@overload
def user_auth(user: None) -> None: ...


def user_auth(user: Optional[User]) -> Optional[httpx.Auth]:
    if user is None:
        return None

    if user.token is not None:
        return BearerAuth(user.token)

    if user.exec:
        return ExecAuth(user.exec)

    if user.username and user.password:
        return httpx.BasicAuth(user.username, user.password)

    if user.auth_provider:
        raise ConfigError("auth-provider not supported")

    # TODO: Is this intended? Previously, a return statement was just missing entirely.
    return None


def user_cert(user: User, abs_file: Callable[[StrOrPath], StrOrPath]) -> Optional[Tuple[StrOrPath, StrOrPath]]:
    """Extract user certificates"""
    if user.client_cert or user.client_cert_data:
        return (
            FileStr(user.client_cert_data) or abs_file(user.client_cert),  # type: ignore[arg-type]
            FileStr(user.client_key_data) or abs_file(user.client_key),  # type: ignore[arg-type]
        )
    return None


def verify_cluster(
    cluster: Cluster,
    user: User,
    abs_file: Callable[[StrOrPath], StrOrPath],
    trust_env: bool = True,
) -> ssl.SSLContext:
    """setup certificate verification"""
    if cluster.certificate_auth:
        ctx = ssl.create_default_context(cafile=abs_file(cluster.certificate_auth))
    elif cluster.certificate_auth_data:
        ctx = ssl.create_default_context(cafile=FileStr(cluster.certificate_auth_data))
    else:
        ctx = httpx.create_ssl_context(verify=not cluster.insecure, trust_env=trust_env)
    cert = user_cert(user, abs_file)
    if cert:
        ctx.load_cert_chain(*cert)
    return ctx
