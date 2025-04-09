# Custom Resources

For simple custom resources, it might be easiest to use [Generic Resources](generic-resources.md).

If you want to work with more complex custom resources, or you want the added type safety of fully defined types, you can define your own Custom Resources.

## Defining your own Custom Resources

First you must define the models that make up your Custom Resource:

```python
from dataclasses import dataclass, field
from typing import Optional

from lightkube.core.dataclasses_dict import DataclassDictMixIn
from lightkube.models import meta_v1


@dataclass
class Owner(DataclassDictMixIn):
    name: str


@dataclass
class DogSpec(DataclassDictMixIn):
    breed: str
    owner: Owner


@dataclass
class DogStatus(DataclassDictMixIn):
    conditions: Optional[list[meta_v1.Condition]] = None
    observedGeneration: Optional[int] = None


@dataclass
class Dog(DataclassDictMixIn):
    apiVersion: Optional[str] = None
    kind: Optional[str] = None
    metadata: Optional[meta_v1.ObjectMeta] = None
    spec: Optional[DogSpec] = None
    status: Optional[DogStatus] = None
```

To be able to use these models as resources in the client, you must create the corresponding `Resource` subclasses:

```python
from typing import ClassVar
from lightkube.core import resource as res
from ..models import dog as m_dog


# Only needed if your custom resource has a status subresource
class DogStatus(res.NamespacedSubResource, m_dog.Dog):
    _api_info = res.ApiInfo(
        resource=res.ResourceDef('stable.example.com', 'v1', 'Dog'),
        parent=res.ResourceDef('stable.example.com', 'v1', 'Dog'),
        plural='dogs',
        verbs=['get', 'patch', 'put'],
        action='status',
    )


class Dog(res.NamespacedResourceG, m_dog.Dog):
    _api_info = res.ApiInfo(
        resource=res.ResourceDef('stable.example.com', 'v1', 'Dog'),
        plural='dogs',
        verbs=[
            'delete', 'deletecollection', 'get', 'global_list', 'global_watch', 
            'list', 'patch', 'post', 'put', 'watch'
        ],
    )

    # Only needed if your custom resource has a status subresource
    Status: ClassVar = DogStatus
```

Once you have defined your custom resource, you can use it with the `Client` as you would with any other resource.
