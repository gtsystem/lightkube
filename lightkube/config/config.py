"""
Configuration code.
"""
import base64
import copy
import os
import tempfile

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

    @classmethod
    def from_service_account(
        cls, path="/var/run/secrets/kubernetes.io/serviceaccount", **kwargs
    ):
        """
        Construct KubeConfig from in-cluster service account.
        """
        with open(os.path.join(path, "namespace")) as fp:
            namespace = fp.read()

        with open(os.path.join(path, "token")) as fp:
            token = fp.read()

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
                        "certificate-authority": os.path.join(path, "ca.crt"),
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
        filename = os.path.expanduser(filename)
        if not os.path.isfile(filename):
            raise exceptions.PyKubeError(
                "Configuration file {} not found".format(filename)
            )
        with open(filename) as f:
            doc = yaml.safe_load(f.read())
        self = cls(doc, **kwargs)
        self.filename = filename
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
    def kubeconfig_file(self):
        """
        Returns the path to kubeconfig file, if it exists
        """
        if not hasattr(self, "filename"):
            return None
        return self.filename

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
                BytesOrFile.maybe_set(c, "certificate-authority", self.kubeconfig_file)
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
                    BytesOrFile.maybe_set(u, "client-certificate", self.kubeconfig_file)
                    BytesOrFile.maybe_set(u, "client-key", self.kubeconfig_file)
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
        if not self.kubeconfig_file:
            # Config was provided as string, not way to persit it
            return
        with open(self.kubeconfig_file, "w") as f:
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
    def maybe_set(cls, d, key, kubeconfig_file):
        file_key = key
        data_key = "{}-data".format(key)
        if data_key in d:
            d[file_key] = cls(data=d[data_key], kubeconfig_file=kubeconfig_file)
            del d[data_key]
        elif file_key in d:
            d[file_key] = cls(filename=d[file_key], kubeconfig_file=kubeconfig_file)

    def __init__(self, filename=None, data=None, kubeconfig_file=None):
        """
        Creates a new instance of BytesOrFile.

        :Parameters:
           - `filename`: A full path to a file
           - `data`: base64 encoded bytes
        """
        self._filename = None
        self._bytes = None
        if filename is not None and data is not None:
            raise TypeError("filename or data kwarg must be specified, not both")
        elif filename is not None:

            # If relative path is given, should be made absolute with respect to the directory of the kube config
            # https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/#file-references
            if not os.path.isabs(filename):
                if kubeconfig_file:
                    filename = os.path.join(os.path.dirname(kubeconfig_file), filename)
                else:
                    raise exceptions.PyKubeError(
                        "{} passed as relative path, but cannot determine location of kube config".format(
                            filename
                        )
                    )

            if not os.path.isfile(filename):
                raise exceptions.PyKubeError(
                    "'{}' file does not exist".format(filename)
                )
            self._filename = filename
        elif data is not None:
            self._bytes = base64.b64decode(data)
        else:
            raise TypeError("filename or data kwarg must be specified")

    def bytes(self):
        """
        Returns the provided data as bytes.
        """
        if self._filename:
            with open(self._filename, "rb") as f:
                return f.read()
        else:
            return self._bytes

    def filename(self):
        """
        Returns the provided data as a file location.
        """
        if self._filename:
            return self._filename
        else:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(self._bytes)
            return f.name