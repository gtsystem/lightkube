"""
Source: https://raw.githubusercontent.com/hjacobs/pykube/master/pykube/http.py
HTTP request related code.
"""
import json
import os
import subprocess
import httpx
from .config import KubeConfig


def Client(config: KubeConfig, timeout: httpx.Timeout = None) -> httpx.Client:
    kwargs = {}
    _setup(config, kwargs, timeout=timeout)
    return httpx.Client(**kwargs)


def AsyncClient(config: KubeConfig, timeout: httpx.Timeout = None) -> httpx.AsyncClient:
    kwargs = {}
    _setup(config, kwargs, timeout=timeout)
    return httpx.AsyncClient(**kwargs)


def _setup(config, kwargs, timeout: httpx.Timeout = None):
    if timeout:
        kwargs['timeout'] = timeout
    kwargs["base_url"] = config.cluster['server']
    _setup_request_auth(config, kwargs)
    _setup_request_certificates(config, kwargs)


def _setup_request_auth(config, kwargs):
    """
    Set up authorization for the request.

    Return an optional function to use as a retry manager if the initial request fails
    with an unauthorized error.
    """

    if config.user.get("token"):
        kwargs.setdefault("headers", {})["Authorization"] = "Bearer {}".format(config.user["token"])
        return None

    if "exec" in config.user:
        exec_conf = config.user["exec"]

        api_version = exec_conf["apiVersion"]
        if api_version in ("client.authentication.k8s.io/v1alpha1", "client.authentication.k8s.io/v1beta1"):
            cmd_env_vars = dict(os.environ)
            for env_var in exec_conf.get("env") or []:
                cmd_env_vars[env_var["name"]] = env_var["value"]

            output = subprocess.check_output(
                [exec_conf["command"]] + exec_conf.get("args", []), env=cmd_env_vars
            )

            parsed_out = json.loads(output)
            token = parsed_out["status"]["token"]
        else:
            raise NotImplementedError(
                f"auth exec api version {api_version} not implemented"
            )

        kwargs.setdefault("headers", {})["Authorization"] = "Bearer {}".format(token)
        return None

    if config.user.get("username") and config.user.get("password"):
        kwargs["auth"] = (config.user["username"], config.user["password"])
        return None

    if "auth-provider" in config.user:
        raise Exception("auth-provider not supported")

    return None


def _setup_request_certificates(config, kwargs):
    if "client-certificate" in config.user:
        kwargs["cert"] = (
            config.user["client-certificate"].filename(),
            config.user["client-key"].filename(),
        )
    # setup certificate verification
    if "certificate-authority" in config.cluster:
        kwargs["verify"] = config.cluster["certificate-authority"].filename()
    elif "insecure-skip-tls-verify" in config.cluster:
        kwargs["verify"] = not config.cluster["insecure-skip-tls-verify"]


