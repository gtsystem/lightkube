import os
import yaml
import tempfile
import base64
from typing import Dict, NamedTuple, Optional
from pathlib import Path

from ..core import exceptions
from .models import Cluster, User, Context

"""
| behavior                  | kubectl                   | lightkube             |
|---------------------------|---------------------------|-----------------------|
| current-context missing   | use proxy                 | fail (conf is None)   |
| current-context wrong     | fail                      | fail                  |
| context.cluster missing   | use proxy                 | fail                  |
| context.user missing      | interactive user/password | no auth set           |
| context.user wrong        | interactive user/password | fail                  |
| context.namespace missing | use default namespace     | use default namespace |
"""


def to_mapping(obj_list, key, factory):
    return {obj['name']: factory.from_dict(obj[key], lazy=False) for obj in obj_list}


DEFAULT_NAMESPACE = "default"
SERVICE_ACCOUNT = "/var/run/secrets/kubernetes.io/serviceaccount"
DEFAULT_KUBECONFIG = "~/.kube/config"


class SingleConfig(NamedTuple):
    context_name: str
    context: Context
    cluster: Cluster
    user: User = None
    fname: Path = None

    @property
    def namespace(self):
        return self.context.namespace or DEFAULT_NAMESPACE

    def abs_file(self, fname):
        if Path(fname).is_absolute():
            return fname

        if self.fname is None:
            raise exceptions.ConfigError(f"{fname} is relative, but kubeconfig path unknown")

        return self.fname.parent.joinpath(fname)


PROXY_CONF = SingleConfig(
    context_name="default", context=Context(cluster="default"),
    cluster=Cluster(server="http://localhost:8080")
)


class KubeConfig:
    """Class to represent a kubeconfig. See the specific constructors depending on your use case."""
    clusters: Dict[str, Cluster]
    users: Dict[str, User]
    contexts: Dict[str, Context]

    def __init__(self, *, clusters, contexts, users=None, current_context=None, fname=None):
        """
        Create the kubernetes configuration manually. Normally this constructor should not be called directly.
        Use a specific constructor instead.

        **Parameters**

        * **clusters**: Dictionary of cluster name -> `Cluster` instance.
        * **contexts**: Dictionary of context name -> `Context` instance.
        * **users**: Dictionary of user name -> `User` instance.
        * **current_context**: Name of the current context.
        * **fname**: Name of the file where the configuration has been readed from.
        """
        self.current_context = current_context
        self.clusters = clusters
        self.contexts = contexts
        self.users = users or {}
        self.fname = Path(fname) if fname else None

    @classmethod
    def from_dict(cls, conf: Dict, fname=None):
        """Creates a KubeConfig instance from the content of a dictionary structure.

        **Parameters**

        * **conf**: Configuration structure, main attributes are `clusters`, `contexts`, `users` and `current-context`.
        * **fname**: File path from where this configuration has been loaded. This is needed to resolve relative paths
          present inside the configuration.
        """
        return cls(
            current_context=conf.get('current-context'),
            clusters=to_mapping(conf['clusters'], 'cluster', factory=Cluster),
            contexts=to_mapping(conf['contexts'], 'context', factory=Context),
            users=to_mapping(conf.get('users', []), 'user', factory=User),
            fname=fname
        )

    def get(self, context_name=None, default: SingleConfig = None) -> Optional[SingleConfig]:
        """Returns a `SingleConfig` instance, representing the configuration matching the given `context_name`.
        Lightkube client will automatically call this method without parameters when an instance of `KubeConfig`
        is provided.

        **Parameters**

        * **context_name**: Name of the context to use. If `context_name` is undefined, the `current-context` is used.
          In the case both contexts are undefined, and the default is provided, this method will return the default.
          It will fail with an error otherwise.
        * **default**: Instance of a `SingleConfig` to be returned in case both contexts are not set. When this
          parameter is not provided and no context is defined, the method call will fail.
        """
        if context_name is None:
            context_name = self.current_context
        if context_name is None:
            if default is None:
                raise exceptions.ConfigError("No current context set and no default provided")
            return default
        try:
            ctx = self.contexts[context_name]
        except KeyError:
            raise exceptions.ConfigError(f"Context '{context_name}' not found")
        return SingleConfig(
            context_name=context_name, context=ctx,
            cluster=self.clusters[ctx.cluster],
            user=self.users[ctx.user] if ctx.user else None,
            fname=self.fname
        )

    @classmethod
    def from_file(cls, fname):
        """Creates an instance of the KubeConfig class from a kubeconfig file in YAML format.

        **Parameters**

         * **fname**: Path to the kuberneted configuration.
        """
        filepath = Path(fname).expanduser()
        if not filepath.is_file():
            raise exceptions.ConfigError(f"Configuration file {fname} not found")
        with filepath.open() as f:
            return cls.from_dict(yaml.safe_load(f.read()), fname=filepath)

    @classmethod
    def from_one(cls, *, cluster, user=None, context_name='default', namespace=None, fname=None):
        """Creates an instance of the KubeConfig class from one cluster and one user configuration"""
        context = Context(cluster=context_name, user=context_name if user else None, namespace=namespace)
        return cls(
            clusters={context_name: cluster},
            contexts={context_name: context},
            users={context_name: user} if user else None,
            current_context=context_name,
            fname=fname
        )

    @classmethod
    def from_server(cls, url, namespace=None):
        """Creates an instance of the KubeConfig class from the cluster server url"""
        return cls.from_one(cluster=Cluster(server=url), namespace=namespace)

    @classmethod
    def from_service_account(cls, service_account=SERVICE_ACCOUNT):
        """Creates a configuration from in-cluster service account information.

        **Parameters**

         * **service_account**: Allows to override the default service account directory path.
           Default `/var/run/secrets/kubernetes.io/serviceaccount`.
        """
        account_dir = Path(service_account)

        try:
            token = account_dir.joinpath("token").read_text()
            namespace = account_dir.joinpath("namespace").read_text()
        except FileNotFoundError as e:
            raise exceptions.ConfigError(str(e))

        host = os.environ["KUBERNETES_SERVICE_HOST"]
        port = os.environ["KUBERNETES_SERVICE_PORT"]
        if ":" in host:     # ipv6
            host = f"[{host}]"
        return cls.from_one(
            cluster=Cluster(
                server=f"https://{host}:{port}",
                certificate_auth=str(account_dir.joinpath("ca.crt"))
            ),
            user=User(token=token),
            namespace=namespace
        )

    @classmethod
    def from_env(cls, service_account=SERVICE_ACCOUNT, default_config=DEFAULT_KUBECONFIG):
        """Attempts to load the configuration automatically looking at the environment and filesystem.

         The method will attempt to load a configuration using the following order:

         * in-cluster config.
         * config file defined in `KUBECONFIG` environment variable.
         * configuration file present on the default location.

         **Parameters**

         * **service_account**: Allows to override the default service account directory path.
           Default `/var/run/secrets/kubernetes.io/serviceaccount`.
         * **default_config**: Allows to override the default configuration location. Default `~/.kube/config`.
         """
        try:
            return KubeConfig.from_service_account(service_account=service_account)
        except exceptions.ConfigError:
            return KubeConfig.from_file(os.environ.get('KUBECONFIG', default_config))

