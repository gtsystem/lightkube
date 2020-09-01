# lightkube

![](https://img.shields.io/github/workflow/status/gtsystem/lightkube/Python%20package) [![Coverage Status](https://coveralls.io/repos/github/gtsystem/lightkube/badge.svg?branch=master)](https://coveralls.io/github/gtsystem/lightkube?branch=master)

Modern lightweight kubernetes module for python

**NOTICE:** This project is still under development and not suitable for production usage.

## Highlights

* *Simple* interface shared across all kubernetes APIs.
* Extensive *type hints* to avoid common mistakes and to support autocompletion (tested on PyCharm).
* Defines models and resources generated from the swagger specifications. Models are defined using standard dataclasses.
* Lazy instantiation of inner models.
* Fast startup and small memory footprint as only needed models and resources can be loaded.
* Automatic handling of pagination when listing resources.
* Customizable handling of errors when watching resources.

This module is powered by [httpx](https://github.com/encode/httpx/tree/master/httpx). 

## Installation

    pip install lightkube

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

## Upcoming features

* Support for async/await
* Support for loading definitions from yaml files
* Support for installing a specific version of the kubernetes models
