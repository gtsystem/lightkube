# Generic Resources

Sometimes you may need to interact with resources installed in the cluster that are not 
provided by default with a kubernetes installation.
You can still interact with such resources using a generic resource.

## Interface

::: lightkube.generic_resource.create_global_resource
    :docstring:
    
::: lightkube.generic_resource.create_namespaced_resource
    :docstring:

## Examples

```python
from lightkube import Client
from lightkube.generic_resource import create_namespaced_resource

Job = create_namespaced_resource('stable.example.com', 'v1', 'Job', 'jobs')

client = Client()
job = client.get(Job, name="job1", namespace="my-namespace")
```

A generic resource is itself a subclass of `dict` so you can access the content as you would do
with a dictionary:

```python
print(job["path"]["to"]["something"])
```

For conveniency, default resources attributes `apiVersion`, `metadata`, `kind` and `status` can be
accessed using the attribute notation:

```
print(job.kind)
print(job.metadata)
```

Specifically metadata is also decoded using the model ``models.meta_v1.ObjectMeta``:

`print(job.metadata.name)`

Since it's a dictionary you can create a resource manually as follow:

```python
job = Job(metadata={"name": "job2", "namespace": "my-namespace"}, spec=...)
client.create(job)
```

!!! note
    Since generic resources are schemaless, more attention need to be given to what 
    attributes are available or you will get an error from the server.

Subresources `Status` and `Scale` are also defined:

```python
job = client.get(Job.Status, name="job1", namespace="my-namespace")
```

!!! note
    Only some resources may support `Scale`.
 