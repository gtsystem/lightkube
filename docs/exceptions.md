# Exceptions

Lightkube uses httpx for handling http requests and responses. 
Because of that, connectivity or timeout issues may raise exceptions. 
You can get familiar with the exceptions returned by httpx library [here](https://www.python-httpx.org/exceptions/).

There are few lightkube specific exceptions:

::: lightkube.ConfigError

This exception is raised if a failure is encountered handling the kubernetes configuration:

```python
from lightkube import Client, ConfigError

try:
    client = Client()
except ConfigError as e:
    print(e)
```

output:

```bash
Configuration file ~/.kube/config not found
```


::: lightkube.ApiError

This exception extends [`httpx.HTTPStatusError`](https://www.python-httpx.org/exceptions/) and is raised when an HTTP error is
returned from kubernetes API. An extra `status` attribute is available with details
about the failure using the standard model [`meta_v1.Status`](https://gtsystem.github.io/lightkube-models/1.19/models/meta_v1/#status).

```python
from lightkube import Client, ApiError

client = Client()
try:
    pod = client.get(Pod, name="not-existing-pod")
except ApiError as e:
    print(e.status)
```

output:

```python
Status(
    apiVersion='v1', 
    code=404, 
    details=StatusDetails(
        causes=None, group=None, kind='pods', 
        name='not-existing-pod', retryAfterSeconds=None, uid=None
    ),
    kind='Status', 
    message='pods "not-existing-pod" not found', 
    metadata=ListMeta(
        continue_=None, remainingItemCount=None, resourceVersion=None, selfLink=None
    ),
    reason='NotFound',
    status='Failure'
)
```


::: lightkube.LoadResourceError

This exception can be raised when loading an undefined resource using `codecs.from_dict()`
or `codecs.load_all_yaml()` (See [Load/Dump kubernetes objects](codecs.md)).


::: lightkube.NotReadyError

This exception is raised when attempting to access the list response attribute `resourceVersion` 
before the list has been consumed. For more details see [List-Watch pattern](list-watch.md)


::: lightkube.exceptions.ObjectDeleted

This exception is raised when waiting for an object condition using `client.wait(...)`, 
but the object itself get deleted. This is to prevent an infinite wait.


::: lightkube.exceptions.ConditionError

This exception is raised when waiting for an object condition using `client.wait(...)`,
if the condition matches one of the conditions in `raise_for_conditions` parameter.


