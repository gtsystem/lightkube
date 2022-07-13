# Generic Resources

Sometimes you may need to interact with resources installed in the cluster that are not 
provided by default with a kubernetes installation.
You can still interact with such resources using a generic resource.

## Interface

::: lightkube.generic_resource.create_global_resource
    :docstring:
    
::: lightkube.generic_resource.create_namespaced_resource
    :docstring:

### Examples

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
 
## Convenience Functions for Generic Resources

Some helper functions are also included to make using generic resources easier:

::: lightkube.generic_resource.get_generic_resource
    :docstring:

::: lightkube.generic_resource.load_in_cluster_generic_resources
    :docstring:

::: lightkube.generic_resource.async_load_in_cluster_generic_resources
    :docstring:

::: lightkube.generic_resource.create_resources_from_crd
    :docstring:

`load_in_cluster_generic_resources` loads all CRDs in the cluster as generic resources, removing the need for explicitly defining each resource needed.  This is especially helpful for scripting around YAML files that may use unknown custom resources.  For example, using the [Kubernetes example of the CronTab CRD](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/):

crontab.yaml:
```yaml
apiVersion: "stable.example.com/v1"
kind: CronTab
metadata:
  name: my-new-cron-object
spec:
  cronSpec: "* * * * */5"
  image: my-awesome-cron-image
```

```python
from pathlib import Path

from lightkube import Client
from lightkube.codecs import load_all_yaml
from lightkube.generic_resource import load_in_cluster_generic_resources

# This fails with error message:
# lightkube.core.exceptions.LoadResourceError: No module named 'lightkube.resources.stable_example_com_v1'. If using a CRD, ensure you define a generic resource.
resources = load_all_yaml(Path("crontab.yaml").read_text())

client = Client()
load_in_cluster_generic_resources(client)

# Now we can load_all_yaml (and use those loaded resources, for example to create them in cluster)
resources = load_all_yaml(Path("crontab.yaml").read_text())
```

`create_resource_from_crd` creates generic resources for each version of a `CustomResourceDefinition` object.  For example:

```python
from lightkube.generic_resource import create_resources_from_crd
from lightkube.resources.apiextensions_v1 import CustomResourceDefinition
from lightkube.models.apiextensions_v1 import (
    CustomResourceDefinitionNames,
    CustomResourceDefinitionSpec,
    CustomResourceDefinitionVersion,
)
versions = ['v1alpha1', 'v1']

crd = CustomResourceDefinition(
    
    spec=CustomResourceDefinitionSpec(
        group='some.group',
        names=CustomResourceDefinitionNames(
            kind='somekind',
            plural='somekinds',
        ),
        scope='Namespaced',
        versions=[
            CustomResourceDefinitionVersion(
                name=version,
                served=True,
                storage=True,
            ) for version in versions
        ],
    )
)

create_resources_from_crd(crd)  # Creates two generic resources, one for each above version

# To demonstrate this worked:
from lightkube.generic_resource import _created_resources
print("Dict of custom resources that have been defined in Lightkube:")
print(_created_resources)
```
