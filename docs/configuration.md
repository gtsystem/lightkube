# Configuration

Similar to other Kubernetes libraries and the `kubectl` CLI tool,
lightkube utilizes the kubeconfig file to configure the connection
with Kubernetes. 

The kubernetes configuration is represented by the class [lightkube.KubeConfig][].

## Load the configuration from a file

The constructor `KubeConfig.from_file()` is used to load a specific configuration from the filesystem (which needs to follow
the standard YAML kubeconfig format).

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

The in-cluster configuration automatically supports **token refresh**. Kubernetes rotates projected service account
tokens before they expire, and lightkube will re-read the token from the mounted file whenever the API server returns a
`401 Unauthorized` response. This ensures long-running controllers and operators continue to work without restarts, even
with short-lived tokens.

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

## Closing the client

Both `Client` and `AsyncClient` hold an underlying httpx connection pool that should be closed
when the client is no longer needed, in order to release open file descriptors.

The recommended approach is to use the client as a context manager:

```python
from lightkube import Client

with Client() as client:
    pod = client.get(Pod, name="my-pod")
```

```python
from lightkube import AsyncClient

async with AsyncClient() as client:
    pod = await client.get(Pod, name="my-pod")
```

You can also close the client explicitly:

```python
client = Client()
try:
    pod = client.get(Pod, name="my-pod")
finally:
    client.close()
```

```python
client = AsyncClient()
try:
    pod = await client.get(Pod, name="my-pod")
finally:
    await client.aclose()  # or await client.close()
```

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
