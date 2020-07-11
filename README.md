# lightkube

![](https://img.shields.io/github/workflow/status/gtsystem/lightkube/Python%20package) [![Coverage Status](https://coveralls.io/repos/github/gtsystem/lightkube/badge.svg?branch=master)](https://coveralls.io/github/gtsystem/lightkube?branch=master)

Modern lightweight kubernetes module for python

**NOTICE:** This project is still in an early alpha stage and not suitable for production usage.

## Usage

Read a pod

```python
from lightkube import Client
from lightkube.resources.core_v1 import Pod

client = Client()
pod = client.get(Pod, name="my-pod", namespace="default")
print(pod.namespace.uid)
```

List nodes
```python
from lightkube import Client
from lightkube.resources.core_v1 import Node

client = Client()
for node in client.list(Node):
    print(node.metadata.name)
```

Watch deployments
```python
from lightkube import Client
from lightkube.resources.apps_v1 import Deployment

client = Client()
for op, dep in client.watch(Deployment, namespace="default"):
    print(f"{dep.namespace.name} {dep.spec.replicas}")
```

Create a config map
```python
from lightkube.resources.core_v1 import ConfigMap
from lightkube.models.meta_v1 import ObjectMeta

config = ConfigMap(
    metadata=ObjectMeta(name='my-config', namespace='default'),
    data={'key1': 'value1', 'key2': 'value2'}
)

client.create(config)
```

Replace the previous config with a different content
```python
config.data['key1'] = 'new value'
client.replace(config)
```

Patch an existing config
```python
patch = {'metadata': {'labels': {'app': 'xyz'}}}
client.patch(ConfigMap, name='my-config', namespace='default', obj=patch)
```

Delete a namespaced resource
```python
client.delete(ConfigMap, name='my-config', namespace='default')
```

Scale a deployment
```python
from lightkube.resources.apps_v1 import Deployment
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.models.autoscaling_v1 import ScaleSpec

obj = Deployment.Scale(
    metadata=ObjectMeta(name='metrics-server', namespace='kube-system'),
    spec=ScaleSpec(replicas=1)
)
client.replace(obj, 'metrics-server', namespace='kube-system')
```
