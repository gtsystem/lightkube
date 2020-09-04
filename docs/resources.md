# Resources

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

## Subresources

Some kubernetes resources provide extra subresources like `/status`.
Subresources can be found as attributes of the corresponding resource class.
For example `Deployment` provides `Deployment.Status` and `Deployment.Scale`. 
Similar to resources, subresources can be used directly with the lightkube client.
