"""
Configuration code.

original source: https://github.com/hjacobs/pykube/tree/20.7.2
"""
import base64
import copy
import os
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from ..core import exceptions


def _join_host_port(host, port):
    """Adapted golang's net.JoinHostPort"""
    template = "{}:{}"
    host_requires_bracketing = ":" in host or "%" in host
    if host_requires_bracketing:
        template = "[{}]:{}"
    return template.format(host, port)


class KubeConfig:
    """
    Main configuration class.
    """

    filepath = None

    @classmethod
    def from_service_account(
        cls, path="/var/run/secrets/kubernetes.io/serviceaccount", **kwargs
    ):
        """
        Construct KubeConfig from in-cluster service account.
        """
        service_account_dir = Path(path)

        with service_account_dir.joinpath("token").open() as fp:
            token = fp.read()

        with service_account_dir.joinpath("namespace").open() as fp:
            namespace = fp.read()

        host = os.environ.get("PYKUBE_KUBERNETES_SERVICE_HOST")
        if host is None:
            host = os.environ["KUBERNETES_SERVICE_HOST"]
        port = os.environ.get("PYKUBE_KUBERNETES_SERVICE_PORT")
        if port is None:
            port = os.environ["KUBERNETES_SERVICE_PORT"]
        doc = {
            "clusters": [
                {
                    "name": "self",
                    "cluster": {
                        "server": "https://" + _join_host_port(host, port),
                        "certificate-authority": str(
                            service_account_dir.joinpath("ca.crt")
                        ),
                    },
                }
            ],
            "users": [{"name": "self", "user": {"token": token}}],
            "contexts": [
                {
                    "name": "self",
                    "context": {
                        "cluster": "self",
                        "user": "self",
                        "namespace": namespace,
                    },
                }
            ],
            "current-context": "self",
        }
        self = cls(doc, **kwargs)
        return self

    @classmethod
    def from_file(cls, filename=None, **kwargs):
        """
        Creates an instance of the KubeConfig class from a kubeconfig file.

        :param filename: The full path to the configuration file. Defaults to ~/.kube/config
        """
        if not filename:
            filename = os.getenv("KUBECONFIG", "~/.kube/config")
        filepath = Path(filename).expanduser()
        if not filepath.is_file():
            raise exceptions.PyKubeError(
                "Configuration file {} not found".format(filename)
            )
        with filepath.open() as f:
            doc = yaml.safe_load(f.read())
        self = cls(doc, **kwargs)
        self.filepath = filepath
        return self

    @classmethod
    def from_env(cls):
        """
        Convenience function to create an instance of KubeConfig from the current environment.

        First tries to use in-cluster ServiceAccount, then tries default ~/.kube/config (or KUBECONFIG)
        """
        try:
            # running in cluster
            config = cls.from_service_account()
        except FileNotFoundError:
            # not running in cluster => load local ~/.kube/config
            config = cls.from_file()
        return config

    @classmethod
    def from_url(cls, url, **kwargs):
        """
        Creates an instance of the KubeConfig class from a single URL (useful
        for interacting with kubectl proxy).
        """
        doc = {
            "clusters": [{"name": "self", "cluster": {"server": url}}],
            "contexts": [{"name": "self", "context": {"cluster": "self"}}],
            "current-context": "self",
        }
        self = cls(doc, **kwargs)
        return self

    def __init__(self, doc, current_context=None):
        """
        Creates an instance of the KubeConfig class.
        """
        self.doc = doc
        self._current_context = None
        if current_context is not None:
            self.set_current_context(current_context)
        elif "current-context" in doc and doc["current-context"]:
            self.set_current_context(doc["current-context"])

    def set_current_context(self, value):
        """
        Sets the context to the provided value.

        :Parameters:
           - `value`: The value for the current context
        """
        self._current_context = value

    @property
    def kubeconfig_path(self) -> Optional[Path]:
        """
        Returns the path to kubeconfig file, if it exists
        """
        if not hasattr(self, "filepath"):
            return None
        return self.filepath

    @property
    def kubeconfig_file(self) -> Optional[str]:
        """
        Returns the path to kubeconfig file as string, if it exists
        """
        if not hasattr(self, "filepath"):
            return None
        return str(self.filepath)

    @property
    def current_context(self):
        if self._current_context is None:
            raise exceptions.PyKubeError(
                "current context not set; call set_current_context"
            )
        return self._current_context

    @property
    def clusters(self):
        """
        Returns known clusters by exposing as a read-only property.
        """
        if not hasattr(self, "_clusters"):
            cs = {}
            for cr in self.doc["clusters"]:
                cs[cr["name"]] = c = copy.deepcopy(cr["cluster"])
                if "server" not in c:
                    c["server"] = "http://localhost"
                BytesOrFile.maybe_set(c, "certificate-authority", self.kubeconfig_path)
            self._clusters = cs
        return self._clusters

    @property
    def users(self):
        """
        Returns known users by exposing as a read-only property.
        """
        if not hasattr(self, "_users"):
            us = {}
            if "users" in self.doc:
                for ur in self.doc["users"]:
                    us[ur["name"]] = u = copy.deepcopy(ur["user"])
                    BytesOrFile.maybe_set(u, "client-certificate", self.kubeconfig_path)
                    BytesOrFile.maybe_set(u, "client-key", self.kubeconfig_path)
            self._users = us
        return self._users

    @property
    def contexts(self):
        """
        Returns known contexts by exposing as a read-only property.
        """
        if not hasattr(self, "_contexts"):
            cs = {}
            for cr in self.doc["contexts"]:
                cs[cr["name"]] = copy.deepcopy(cr["context"])
            self._contexts = cs
        return self._contexts

    @property
    def cluster(self):
        """
        Returns the current selected cluster by exposing as a
        read-only property.
        """
        return self.clusters[self.contexts[self.current_context]["cluster"]]

    @property
    def user(self):
        """
        Returns the current user set by current context
        """
        return self.users.get(self.contexts[self.current_context].get("user", ""), {})

    @property
    def namespace(self) -> str:
        """
        Returns the current context namespace by exposing as a read-only property.
        """
        return self.contexts[self.current_context].get("namespace", "default")

    def persist_doc(self):

        if not self.kubeconfig_path:
            # Config was provided as string, not way to persit it
            return
        with self.kubeconfig_path.open("w") as f:
            yaml.safe_dump(
                self.doc,
                f,
                encoding="utf-8",
                allow_unicode=True,
                default_flow_style=False,
            )

    def reload(self):
        if hasattr(self, "_users"):
            delattr(self, "_users")
        if hasattr(self, "_contexts"):
            delattr(self, "_contexts")
        if hasattr(self, "_clusters"):
            delattr(self, "_clusters")


class BytesOrFile:
    """
    Implements the same interface for files and byte input.
    """

    @classmethod
    def maybe_set(cls, d, key, kubeconfig_path):
        file_key = key
        data_key = "{}-data".format(key)
        if data_key in d:
            d[file_key] = cls(data=d[data_key], kubeconfig_path=kubeconfig_path)
            del d[data_key]
        elif file_key in d:
            d[file_key] = cls(filename=d[file_key], kubeconfig_path=kubeconfig_path)

    def __init__(self, filename=None, data=None, kubeconfig_path=None):
        """
        Creates a new instance of BytesOrFile.

        :Parameters:
           - `filename`: A full path to a file
           - `data`: base64 encoded bytes
        """
        self._path = None
        self._bytes = None
        if filename is not None and data is not None:
            raise TypeError("filename or data kwarg must be specified, not both")
        elif filename is not None:

            path = Path(filename)
            # If relative path is given, should be made absolute with respect to the directory of the kube config
            # https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/#file-references
            if not path.is_absolute():
                if kubeconfig_path:
                    path = kubeconfig_path.parent.joinpath(path)
                else:
                    raise exceptions.PyKubeError(
                        "{} passed as relative path, but cannot determine location of kube config".format(
                            filename
                        )
                    )

            if not path.is_file():
                raise exceptions.PyKubeError(
                    "'{}' file does not exist".format(filename)
                )
            self._path = path
        elif data is not None:
            self._bytes = base64.b64decode(data)
        else:
            raise TypeError("filename or data kwarg must be specified")

    def bytes(self):
        """
        Returns the provided data as bytes.
        """
        if self._path:
            with self._path.open("rb") as f:
                return f.read()
        else:
            return self._bytes

    def filename(self):
        """
        Returns the provided data as a file location.
        """
        if self._path:
            return str(self._path)
        else:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(self._bytes)
            return f.name
