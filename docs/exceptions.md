# Exception

Lightkube uses httpx for http requests/response. 
You can get familiar with the exceptions returnd by this library [here](https://www.python-httpx.org/exceptions/).

There are two lightkube specific exceptions:

## ConfigError

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

## ApiError

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

## LoadResourceError

This exception can be raised when loading an undefined resource using `codecs.from_dict()`
or `codecs.load_all_yaml()` (See [Load/Dump kubernetes objects](codecs.md)).
