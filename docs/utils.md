# Utils

## Convert quantity string to decimal

K8s converts user input
[quantities](https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/quantity/)
to "canonical form":

> Before serializing, Quantity will be put in "canonical form". This means that
> Exponent/suffix will be adjusted up or down (with a corresponding increase or
> decrease in Mantissa) such that: a. No precision is lost b. No fractional
> digits will be emitted c. The exponent (or suffix) is as large as possible.
> The sign will be omitted unless the number is negative.
>
> Examples: 1.5 will be serialized as "1500m" 1.5Gi will be serialized as "1536Mi"

Additional examples:

| User input                       | K8s representation            |
|----------------------------------|-------------------------------|
| `{"memory": "0.9Gi"}`            | `{"memory": "966367641600m"}` |
| `{"cpu": "0.30000000000000004"}` | `{"cpu": "301m"}`             |

You may need to compare different quantities when interacting with K8s.

## Interface

::: lightkube.utils.quantity.parse_quantity
    :docstring:

## Examples

After patching a statefulset's resource limits you may want to compare
user's input to the statefulset's template to the active podspec:

```python
>>> from lightkube import Client
>>> from lightkube.models.apps_v1 import StatefulSetSpec
>>> from lightkube.models.core_v1 import (
...     Container,
...     PodSpec,
...     PodTemplateSpec,
...     ResourceRequirements,
... )
>>> from lightkube.resources.apps_v1 import StatefulSet
>>> from lightkube.resources.core_v1 import Pod
>>> from lightkube.types import PatchType
>>>
>>> resource_reqs = ResourceRequirements(
...     limits={"cpu": "0.8", "memory": "0.9Gi"},
...     requests={"cpu": "0.4", "memory": "0.5Gi"},
... )
>>>
>>> client = Client()
>>> statefulset = client.get(StatefulSet, name="prom", namespace="mdl")
>>>
>>> delta = StatefulSet(
...     spec=StatefulSetSpec(
...         selector=statefulset.spec.selector,
...         serviceName=statefulset.spec.serviceName,
...         template=PodTemplateSpec(
...             spec=PodSpec(
...                 containers=[Container(name="prometheus", resources=resource_reqs)]
...             )
...         ),
...     )
... )
>>>
>>> client.patch(
...     StatefulSet,
...     "prom",
...     delta,
...     namespace="mdl",
...     patch_type=PatchType.APPLY,
...     field_manager="just me",
... )
>>>
>>> client.get(StatefulSet, name="prom", namespace="mdl").spec.template.spec.containers[1].resources
ResourceRequirements(limits={'cpu': '800m', 'memory': '966367641600m'}, requests={'cpu': '400m', 'memory': '512Mi'})
>>>
>>> pod = client.get(Pod, name="prom-0", namespace="mdl")
>>> pod.spec.containers[1].resources
ResourceRequirements(limits={'cpu': '800m', 'memory': '966367641600m'}, requests={'cpu': '400m', 'memory': '512Mi'})
>>>
>>> from lightkube.utils.quantity import parse_quantity
>>> parse_quantity(pod.spec.containers[1].resources.requests["memory"])
Decimal('536870912.000')
>>> parse_quantity(pod.spec.containers[1].resources.requests["memory"]) == parse_quantity(resource_reqs.requests["memory"])
True
```
