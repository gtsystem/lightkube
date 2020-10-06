# Configuration

Similar to other Kubernetes libraries and the `kubectl` CLI tool,
lightkube utilizes the kubeconfig file to configure the connection
with Kubernetes. 

The kubernetes configuration is represented by the class [lightkube.KubeConfig](client.md#kubeconfig).

## Load the configuration from a file

The constructor `KubeConfig.from_file()` is used to load a specific configuration from the filesystem.

Example:

```python
from lightkube import KubeConfig, Client

config = KubeConfig.from_file("path/to/my/config")
client = Client(config=config)
```

Notice that we didn't select a context. By default the client will pick the current context. This is in fact equivalent to

```python
from lightkube import KubeConfig, Client

config = KubeConfig.from_file("path/to/my/config")
client = Client(config=config.get())    # pick the current context
```

The method `.get()` of KubeConfig is used to select a specific `cluster` and `user` configuration given a defined context.
Without parameters the current context is assumed. A different context can be also used as follow

```python
# use the context named my-context
client = Client(config=config.get(context_name='my-context'))  
```

## Load in-cluster configuration

The constructor `KubeConfig.from_service_account()` is used to build a configuration starting from the service account
data exposed inside a pod running on the cluster:

```python
from lightkube import KubeConfig, Client

config = KubeConfig.from_service_account()
client = Client(config=config)
```

## Auto-detect configuration from the environment

By default lightkube will do his best to detect the configuration looking
at the environment.

```python
import lightkube

client = lightkube.Client() # no configuration provided
```

is equivalent to

```python
from lightkube import KubeConfig, Client

config = KubeConfig.from_env()
client = Client(config=config)
```

`KubeConfig.from_env()` will attempt to load a configuration using the following order:

* in-cluster config.
* config file defined in `KUBECONFIG` environment variable.
* configuration file present on the default location (`~/.kube/config`).

## Proxy configuration

The constructor `KubeConfig.from_server()` will build a simple configuration useful to connect to a non protected
Kubernetes API. This is for example useful to tunnel API calls using kubectl proxy:

```bash
kubectl proxy --port=8080
```

```python
from lightkube import KubeConfig, Client

config = KubeConfig.from_server("http://localhost:8080")
client = Client(config=config)
```
