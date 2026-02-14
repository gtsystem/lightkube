# lightkube

![](https://img.shields.io/github/actions/workflow/status/gtsystem/lightkube/python-package.yml?branch=master)
[![Coverage Status](https://coveralls.io/repos/github/gtsystem/lightkube/badge.svg?branch=master)](https://coveralls.io/github/gtsystem/lightkube?branch=master)
[![pypi supported versions](https://img.shields.io/pypi/pyversions/lightkube.svg)](https://pypi.python.org/pypi/lightkube)

Modern lightweight kubernetes module for python


## Highlights

* *Simple* interface shared across all kubernetes APIs.
* Extensive *type hints* to avoid common mistakes and to support autocompletion.
* Models and resources generated from the swagger specifications using standard dataclasses.
* Load/Dump resource objects from YAML.
* Support for async/await
* Support for installing a specific version of the kubernetes models (1.20 to 1.35)
* Lazy instantiation of inner models.
* Fast startup and small memory footprint as only needed models and resources can be imported.
* Automatic handling of pagination when listing resources.

This module is powered by [httpx](https://github.com/encode/httpx/tree/master/httpx). 

## Installation

This module requires python >= 3.8 

=== "pip"
    ```sh
    pip install lightkube
    ```

=== "uv"
    ```sh
    uv add lightkube
    ```

## Usage

Read a pod

=== "Sync"
    ```python
    from lightkube import Client
    from lightkube.resources.core_v1 import Pod

    client = Client()
    pod = client.get(Pod, name="my-pod", namespace="default")
    print(pod.namespace.uid)
    ```

=== "Async"
    ```python
    from lightkube import AsyncClient
    from lightkube.resources.core_v1 import Pod

    async def example():
        client = AsyncClient()
        pod = await client.get(Pod, name="my-pod", namespace="default")
        print(pod.namespace.uid)
    ```

List nodes

=== "Sync"
    ```python
    from lightkube import Client
    from lightkube.resources.core_v1 import Node

    client = Client()
    for node in client.list(Node):
        print(node.metadata.name)
    ```

=== "Async"
    ```python
    from lightkube import AsyncClient
    from lightkube.resources.core_v1 import Node

    async def example():
        client = AsyncClient()
        async for node in client.list(Node):
            print(node.metadata.name)
    ```

Watch deployments

=== "Sync"
    ```python
    from lightkube import Client
    from lightkube.resources.apps_v1 import Deployment

    client = Client()
    for op, dep in client.watch(Deployment, namespace="default"):
        print(f"{dep.namespace.name} {dep.spec.replicas}")
    ```

=== "Async"
    ```python
    from lightkube import AsyncClient
    from lightkube.resources.apps_v1 import Deployment

    async def example():
        client = AsyncClient()
        async for op, dep in client.watch(Deployment, namespace="default"):
            print(f"{dep.namespace.name} {dep.spec.replicas}")
    ```

Create a config map

=== "Sync"
    ```python
    from lightkube import Client
    from lightkube.resources.core_v1 import ConfigMap
    from lightkube.models.meta_v1 import ObjectMeta

    client = Client()
    config = ConfigMap(
        metadata=ObjectMeta(name='my-config', namespace='default'),
        data={'key1': 'value1', 'key2': 'value2'}
    )

    client.create(config)
    ```

=== "Async"
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

=== "Sync"
    ```python
    config.data['key1'] = 'new value'
    client.replace(config)
    ```

=== "Async"
    ```python
    config.data['key1'] = 'new value'
    await client.replace(config)
    ```

Patch an existing config adding more data

=== "Sync"
    ```python
    patch = {"data": {"key3": "value3"}}
    client.patch(ConfigMap, name="my-config", obj=patch)
    ```

=== "Async"
    ```python
    patch = {"data": {"key3": "value3"}}
    await client.patch(ConfigMap, name='my-config', obj=patch)
    ```

Remove the just added data key `key3`

=== "Sync"
    ```python
    # When using PatchType.MERGE, setting a value of a key/value to None, will remove the current item 
    patch = {'metadata': {"key3": None}}
    client.patch(ConfigMap, name='my-config', namespace='default', obj=patch, patch_type=PatchType.MERGE)
    ```

=== "Async"
    ```python
    # When using PatchType.MERGE, setting a value of a key/value to None, will remove the current item 
    patch = {'metadata': {"key3": None}}
    await client.patch(ConfigMap, name='my-config', namespace='default', obj=patch, patch_type=PatchType.MERGE)
    ```

Add a label

=== "Sync"
    ```python
    client.set(ConfigMap, name="my-config", labels={'env': 'prod'})
    ```

=== "Async"
    ```python
    await client.set(ConfigMap, name="my-config", labels={'env': 'prod'})
    ```

Remove a label

=== "Sync"
    ```python
    client.set(ConfigMap, name="my-config", labels={'env': None})
    ```

=== "Async"
    ```python
    await client.set(ConfigMap, name="my-config", labels={'env': None})
    ```

Delete a namespaced resource

=== "Sync"
    ```python
    client.delete(ConfigMap, name='my-config', namespace='default')
    ```

=== "Async"
    ```python
    await client.delete(ConfigMap, name='my-config', namespace='default')
    ```

Create resources defined in a file

=== "Sync"
    ```python
    from lightkube import Client, codecs

    client = Client()
    with open('deployment.yaml') as f:
        for obj in codecs.load_all_yaml(f):
            client.create(obj)
    ```

=== "Async"
    ```python
    from lightkube import AsyncClient, codecs

    async def example():
        client = AsyncClient()
        with open('deployment.yaml') as f:
            for obj in codecs.load_all_yaml(f):
                await client.create(obj)
    ```

Scale a deployment

=== "Sync"
    ```python
    from lightkube import Client
    from lightkube.resources.apps_v1 import Deployment
    from lightkube.models.meta_v1 import ObjectMeta
    from lightkube.models.autoscaling_v1 import ScaleSpec

    client = Client()
    obj = Deployment.Scale(
        metadata=ObjectMeta(name='metrics-server', namespace='kube-system'),
        spec=ScaleSpec(replicas=1)
    )
    client.replace(obj)
    ```

=== "Async"
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

=== "Sync"
    ```python
    from lightkube import Client
    from lightkube.resources.apps_v1 import Deployment
    from lightkube.models.apps_v1 import DeploymentStatus

    client = Client()
    obj = Deployment.Status(
        status=DeploymentStatus(observedGeneration=99)
    )
    client.apply(obj, name='metrics-server', namespace='kube-system')
    ```

=== "Async"
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


Create and modify resources using [server side apply](https://kubernetes.io/docs/reference/using-api/server-side-apply/)

*Note:* `field_manager` is required for server-side apply. You can specify it once in the client constructor
or when calling `apply()`. Also `apiVersion` and `kind` need to be provided as part of
the object definition.

=== "Sync"
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

=== "Async"
    ```python
    from lightkube import AsyncClient
    from lightkube.resources.core_v1 import ConfigMap
    from lightkube.models.meta_v1 import ObjectMeta

    async def example():
        client = AsyncClient(field_manager="my-manager")
        config = ConfigMap(
            apiVersion='v1', kind='ConfigMap',
            metadata=ObjectMeta(name='my-config', namespace='default'),
            data={'key1': 'value1', 'key2': 'value2'}
        )

        res = await client.apply(config)
        print(res.data)
        # prints {'key1': 'value1', 'key2': 'value2'}

        del config.data['key1']
        config.data['key3'] = 'value3'

        res = await client.apply(config)
        print(res.data)
        # prints {'key2': 'value2', 'key3': 'value3'}
    ```

Stream pod logs

=== "Sync"
    ```python
    from lightkube import Client

    client = Client()
    for line in client.log('my-pod', follow=True):
        print(line)
    ```

=== "Async"
    ```python
    from lightkube import AsyncClient

    async def example():
        client = AsyncClient()
        async for line in client.log('my-pod', follow=True):
            print(line)
    ```

Execute a command inside a pod

=== "Sync"
    ```python
    from lightkube import Client

    client = Client()

    # Capture stdout or raise ApiError if error code is != 0
    res = client.exec('my-pod', namespace='default', command=['ls', '-l', '/'], 
        stdout=True, raise_on_error=True)
    print(res.stdout)

    # Send data to stdin and capture output
    res = client.exec('my-pod', namespace='default', command=['cat'], 
        stdin='hello\n', stdout=True)
    print(res.stdout)
    print(res.exit_code)
    ```

=== "Async"
    ```python
    from lightkube import AsyncClient

    async def example():
        client = AsyncClient()

        # List a directory
        res = await client.exec('my-pod', namespace='default', command=['ls', '-l', '/'], 
            stdout=True, raise_on_error=True)
        print(res.stdout)

        # Send data to stdin and capture output
        res = await client.exec('my-pod', namespace='default', command=['cat'], 
            stdin='hello\n', stdout=True)
        print(res.stdout)
        print(res.exit_code)
    ```

## Unsupported features

The following features are not supported at the moment:

* Special subresources `attach`, `portforward` and `proxy`.
* `auth-provider` authentication method is not supported. The supported authentication methods are `token`, `username` + `password` and `exec`.

