# lightkube

![](https://img.shields.io/github/workflow/status/gtsystem/lightkube/Python%20package)
[![Coverage Status](https://coveralls.io/repos/github/gtsystem/lightkube/badge.svg?branch=master)](https://coveralls.io/github/gtsystem/lightkube?branch=master)
[![pypi supported versions](https://img.shields.io/pypi/pyversions/lightkube.svg)](https://pypi.python.org/pypi/lightkube)

Modern lightweight kubernetes module for python

**NOTICE:** This project is still under development and not suitable for production usage.

## Highlights

* *Simple* interface shared across all kubernetes APIs.
* Extensive *type hints* to avoid common mistakes and to support autocompletion.
* Models and resources generated from the swagger specifications using standard dataclasses.
* Load/Dump resource objects from YAML.
* Support for async/await
* Support for installing a specific version of the kubernetes models (1.15 to 1.26)
* Lazy instantiation of inner models.
* Fast startup and small memory footprint as only needed models and resources can be imported.
* Automatic handling of pagination when listing resources.

This module is powered by [httpx](https://github.com/encode/httpx/tree/master/httpx). 

## Installation

This module requires python >= 3.7 

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

Create resources defined in a file
```python
from lightkube import Client, codecs

client = Client()
with open('deployment.yaml') as f:
    for obj in codecs.load_all_yaml(f):
        client.create(obj)
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

Create and modify resources using [server side apply](https://kubernetes.io/docs/reference/using-api/server-side-apply/)

*Note:* `field_manager` is required for server-side apply. You can specify it once in the client constructor
or when calling `apply()`. Also `apiVersion` and `kind` need to be provided as part of
the object definition.

```python
from lightkube.resources.core_v1 import ConfigMap
from lightkube.models.meta_v1 import ObjectMeta

client = Client(field_manager="my-manager")
config = ConfigMap(
    # note apiVersion and kind need to be specified for server-side apply
    apiVersion='v1', kind='ConfigMap',
    metadata=ObjectMeta(name='my-config', namespace='default'),
    data={'key1': 'value1', 'key2': 'value2'}
)

res = client.apply(config)
print(res.data)
# prints {'key1': 'value1', 'key2': 'value2'}

del config.data['key1']
config.data['key3'] = 'value3'

res = client.apply(config)
print(res.data)
# prints {'key2': 'value2', 'key3': 'value3'}
```

Stream pod logs
```python
from lightkube import Client

client = Client()
for line in client.log('my-pod', follow=True):
    print(line)
```

## Unsupported features

The following features are not supported at the moment:

* Special subresources `attach`, `exec`, `portforward` and `proxy`.
* `auth-provider` authentication method is not supported. The supported
  authentication methods are `token`, `username` + `password` and `exec`.