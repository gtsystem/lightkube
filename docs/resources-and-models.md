# Resources & Models

## Reference

* lightkube-models [1.28](https://gtsystem.github.io/lightkube-models/1.28)
* lightkube-models [1.27](https://gtsystem.github.io/lightkube-models/1.27)
* lightkube-models [1.26](https://gtsystem.github.io/lightkube-models/1.26)
* lightkube-models [1.25](https://gtsystem.github.io/lightkube-models/1.25)
* lightkube-models [1.24](https://gtsystem.github.io/lightkube-models/1.24)
* lightkube-models [1.23](https://gtsystem.github.io/lightkube-models/1.23)
* lightkube-models [1.22](https://gtsystem.github.io/lightkube-models/1.22)
* lightkube-models [1.21](https://gtsystem.github.io/lightkube-models/1.21)
* lightkube-models [1.20](https://gtsystem.github.io/lightkube-models/1.20)
* lightkube-models [1.19](https://gtsystem.github.io/lightkube-models/1.19)
* lightkube-models [1.18](https://gtsystem.github.io/lightkube-models/1.18)
* lightkube-models [1.17](https://gtsystem.github.io/lightkube-models/1.17)
* lightkube-models [1.16](https://gtsystem.github.io/lightkube-models/1.16)
* lightkube-models [1.15](https://gtsystem.github.io/lightkube-models/1.15)

## Resources

Kubernetes API provides access to several resource kinds organized by version and 
API group. Lightkube represents such resources using classes that can be found inside
the package `lightkube.resources`.

Resources are organized in modules where the name follow the convention `{group}_{version}`.
For example the group `apps` on version `v1` includes the resource kind `Deployment`
and it can be accessed as follow `from lightkube.resources.apps_v1 import Deployment`.

Resource classes can be used to call the lightkube client methods or to instantiate the corresponding
objects.

```python
>>> from lightkube import Client
>>> from lightkube.resources.apps_v1 import Deployment

>>> client = Client()
>>> dep = client.get(Deployment, name="my-deo")
>>> type(dep)
<class 'lightkube.resources.apps_v1.Deployment'>
```

### Subresources

Some kubernetes resources provide extra subresources like `/status`.
Subresources can be found as attributes of the corresponding resource class.
For example `Deployment` provides `Deployment.Status` and `Deployment.Scale`. 
Similar to resources, subresources can be used directly with the lightkube client.

## Models

The package `lightkube.models` provides models for all schemas defined in the kubernetes API.
The models are split in modules in a similar way to resources (i.e. the module name match `{group}_{version}`).
All models are defined using standard python dataclasses and are used
to create or retrieve kubernetes objects.

```python
>>> from lightkube.models.meta_v1 import ObjectMeta
>>> ObjectMeta(name='test', namespace='default')
ObjectMeta(annotations=None, clusterName=None, creationTimestamp=None, deletionGracePeriodSeconds=None, deletionTimestamp=None, finalizers=None, generateName=None, generation=None, initializers=None, labels=None, managedFields=None, name='test', namespace='default', ownerReferences=None, resourceVersion=None, selfLink=None, uid=None)
```

Resources are also subclasses of models but they hold extra information
regarding the way the resource can be accessed.
The lightkube client need such information, so will only accept
resources or resource instances as parameters.

## Versioning

Resource and Models are part of a separate python package named 
`lightkube-models`. This package follows the version of the corresponding
kubernetes API:

    {k8s-version}.{release}

For example the package version `1.15.6.1` match kubernetes version `1.15.6`
at release 1.

Depending on the Kubernetes server in use, the appropriate version
should be selected as follow `lightkube-models>=1.15,<1.16`.

A list of available versions, can be seen on [pypi](https://pypi.org/project/lightkube-models/#history).
