# Load/Dump kubernetes objects

## Convert models from/to dict

All lightkube models allow to convert from/to dicts using the methods `.from_dict()` and 
`.to_dict()`. For example you can create an `ObjectMeta` with

```python
from lightkube.models.meta_v1 import ObjectMeta
meta = ObjectMeta.from_dict({'name': 'my-name', 'labels': {'key': 'value'}})
```

and transform it back with

```python
meta_dict = meta.to_dict()
```

Dict representations can then be serialized/deserialized in JSON or YAML.

## Load resource objects

It is possible to load dynamically a resource object using the function `lightkube.codecs.from_dict()`

```python
from lightkube import codecs

obj = codecs.from_dict({
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {'name': 'config-name', 'labels': {'label1': 'value1'}},
        'data': {
            'file1.txt': 'some content here',
            'file2.txt': 'some other content'
        }
})
print(type(obj))
```

Output: `<class 'lightkube.resources.core_v1.ConfigMap'>`

!!! note
    Only known resources can be loaded. These are either kubernetes [standard resources](resources-and-models.md) 
    or [generic resources](generic-resources.md) manually defined. You can register further resources using
    the [`resource_registry`](#resource-registry).

## Load from YAML

Kubernetes resource defined in a YAML file can be easily loaded using the following function: 

::: lightkube.codecs.load_all_yaml
    :docstring:
   
### Example

```python
from lightkube import Client, codecs

client = Client()
with open('deployment.yaml') as f:
    for obj in codecs.load_all_yaml(f):
        client.create(obj)
```

!!! note
    Only defined resources can be loaded. These are either kubernetes [standard resources](resources-and-models.md) 
    or [generic resources](generic-resources.md) manually defined.

If we have a YAML file that both defines a CRD and loads an instance of it, we can use `create_resources_for_crds=True`, like:

```python
from lightkube import Client, codecs

client = Client()
with open('file-with-crd-and-instance.yaml') as f:
    for obj in codecs.load_all_yaml(f, create_resources_for_crds=True):
        client.create(obj)
```

This results in a generic resource being created for any CustomResourceDefinition in the YAML file.  

It is also possible to create resources from a [jinja2](https://jinja.palletsprojects.com) template 
passing the parameter `context`.

For example assuming `service.tmpl` has the following content:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
  labels:
    run: my-nginx
    env: {{env}}
spec:
  type: NodePort
  ports:
  - port: 8080
    targetPort: 80
    protocol: TCP
  selector:
    run: my-nginx
    env: {{env}}
```

can be used as follow:
```python
with open('service.tmpl') as f:
    # render the template using `context` and return the corresponding resource objects.
    objs = codecs.load_all_yaml(f, context={'env': 'prd'})
    print(objs[0].metadata.labels['env'])  # prints `prd`
```

## Dump to YAML

The function `lightkube.codecs.dump_all_yaml(...)` can be used to dump resource objects as YAML.

::: lightkube.codecs.dump_all_yaml
    :docstring:

### Example

```python
from lightkube.resources.core_v1 import ConfigMap
from lightkube.models.meta_v1 import ObjectMeta
from lightkube import codecs

cm = ConfigMap(
    apiVersion='v1', kind='ConfigMap',
    metadata=ObjectMeta(name='xyz', labels={'x': 'y'})
)
with open('deployment-out.yaml', 'w') as fw:
    codecs.dump_all_yaml([cm], fw)
```

## Sorting resource objects

Sometimes you have a manifest of resources where some depend on others.  For example,
consider, the following `yaml_with_dependencies.yaml` file:

```yaml
kind: ClusterRoleBinding
roleRef:
  kind: ClusterRole
  name: example-cluster-role-binding
subjects:
  - kind: ServiceAccount
    name: example-service-account
...
---
kind: ClusterRole
metadata:
  name: example-cluster-role
...
---
kind: ServiceAccount
metadata:
  name: example-service-account
```

where we have a `ClusterRoleBinding` that uses a `ClusterRole` and `ServiceAccount`. 
In cases like this, the order in which we `apply` these resources matters as the
`ClusterRoleBinding` depends on the others.  To sort these objects so that we do not
encounter API errors when `apply`ing them, use `sort_objects(...)`.

::: lightkube.sort_objects
    :docstring:

Revisiting the example above, we can apply from `yaml_with_dependencies.yaml` by:

```python
from lightkube import Client, codecs, sort_objects

client = Client()
with open('yaml_with_dependencies.yaml') as f:
    objects = codecs.load_all_yaml(f)
    for obj in sort_objects(objects):
        client.create(obj)
```

`sort_objects` orders the objects in a way that is friendly to applying them as a
batch, allowing us to loop through them as normal.

Similarly, problems can arise when deleting a batch of objects.  For example, 
consider the manifest `crs_and_crds.yaml`:

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
...
spec:
  names:
    kind: SomeNewCr
    ...
---
kind: SomeNewCr
metadata:
  name: instance-of-new-cr
```

Deleting this in a loop like above would first delete the `CustomResourceDefinition`,
resulting in all instances of `SomeNewCr` to be deleted implicitly.  When we then
attempted to delete `instance-of-new-cr`, we would encounter an API error.  
Use `codecs.sort_objects(..., reverse=True)` to avoid this issue:

```python
from lightkube import Client, codecs, sort_objects

client = Client()
with open('crs_amd_crds.yaml') as f:
    objects = codecs.load_all_yaml(f)
    for obj in sort_objects(objects, reverse=True):
        client.create(obj)
```

This orders the objects in a way that is friendly for deleting them as a batch.

## Resource Registry

The singleton `resource_registry` allows to register a custom resource, so that it can be used by the load
functions on this module:

```python
from lightkube import codecs

codecs.resource_registry.register(MyCustomResource)

with open('service.yaml') as f:
    # Now `MyCustomResource` can be loaded
    objs = codecs.load_all_yaml(f)
```

`register` can also be used as a decorator:
```python
from lightkube.core.resource import NamespacedResource
from lightkube.codecs import resource_registry

@resource_registry.register
class MyCustomResource(NamespacedResource):
    ...
```

### Reference

::: lightkube.codecs.resource_registry
    :docstring:
    :members:
