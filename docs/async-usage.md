# AsyncClient usage

The AsyncClient allows to perform the same operation that are possible using the Client but in
an asycronous way:

* The operations `create`, `delete`, `deletecollection`, `patch`, `replace`, `get` return a coroutine and need to be used with `await ...`.
* The operations `list` and `watch` return an asynchronous iterable and can be used with `async for ...`.

## Examples

Read a pod

```python
from lightkube import AsyncClient
from lightkube.resources.core_v1 import Pod

async def example():
    client = AsyncClient()
    pod = await client.get(Pod, name="my-pod", namespace="default")
    print(pod.namespace.uid)
```

List nodes
```python
from lightkube import AsyncClient
from lightkube.resources.core_v1 import Node

async def example():
    client = AsyncClient()
    async for node in client.list(Node):
        print(node.metadata.name)
```

Watch deployments
```python
from lightkube import AsyncClient
from lightkube.resources.apps_v1 import Deployment

async def example():
    client = AsyncClient()
    async for op, dep in client.watch(Deployment, namespace="default"):
        print(f"{dep.namespace.name} {dep.spec.replicas}")
```

Create a config map
```python
from lightkube import AsyncClient
from lightkube.resources.core_v1 import ConfigMap
from lightkube.models.meta_v1 import ObjectMeta

async def example():
    client = AsyncClient()
    config = ConfigMap(
        metadata=ObjectMeta(name='my-config', namespace='default'),
        data={'key1': 'value1', 'key2': 'value2'}
    )
    
    await client.create(config)
```

Replace the previous config with a different content
```python
config.data['key1'] = 'new value'
await client.replace(config)
```

Patch an existing config
```python
patch = {'metadata': {'labels': {'app': 'xyz'}}}
await client.patch(ConfigMap, name='my-config', namespace='default', obj=patch)
```

Delete a namespaced resource
```python
await client.delete(ConfigMap, name='my-config', namespace='default')
```

Scale a deployment
```python
from lightkube import AsyncClient
from lightkube.resources.apps_v1 import Deployment
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.models.autoscaling_v1 import ScaleSpec

async def example():
    client = AsyncClient()
    obj = Deployment.Scale(
        metadata=ObjectMeta(name='metrics-server', namespace='kube-system'),
        spec=ScaleSpec(replicas=1)
    )
    await client.replace(obj, 'metrics-server', namespace='kube-system')
```

Update Status of a deployment
```python
from lightkube import AsyncClient
from lightkube.resources.apps_v1 import Deployment
from lightkube.models.apps_v1 import DeploymentStatus

async def example():
    client = AsyncClient()
    obj = Deployment.Status(
        status=DeploymentStatus(observedGeneration=99)
    )
    await client.apply(obj, name='metrics-server', namespace='kube-system')
```


Stream pod logs
```python
from lightkube import AsyncClient

async def example():
    client = AsyncClient()
    async for line in client.log('my-pod', follow=True):
        print(line)
```
