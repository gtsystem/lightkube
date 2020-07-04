# lightkube

Modern lightweight kubernetes module for python

**NOTICE:** This project is still in an early alpha stage and not suitable for production usage.

## Usage

Read a pod

```python
from lightkube import Client
from lightkube.resources.core_v1 import Pod

client = Client()
pod = client.ns.get(Pod, name="my-pod", namespace="default")
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
for op, dep in client.ns.watch(Deployment, namespace="default"):
    print(f"{dep.namespace.name} {dep.spec.replicas}")
```
