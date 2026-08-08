# Migrating from v0.x to v1.x

Lightkube v1 keeps the public client and resource APIs familiar, but changes a
few implementation dependencies and fixes two streaming issues.
Use this guide to check code that uses Lightkube internals, custom resources,
`httpx` types, or retry handlers.

Lightkube v1 requires Python 3.10 or newer. This is also the minimum Python
version required by `httpx2`, which is used by Lightkube v1.

## Migrate from httpx to httpx2

Lightkube v1 is now using [httpx2](https://github.com/pydantic/httpx2) instead of
`httpx`. The change matters if your code passes `httpx` objects into Lightkube
or catches `httpx` exceptions raised by it.

For example, update the HTTP types passed when creating a `Client`:

```python
# v0
import httpx
from lightkube import Client

transport: httpx.BaseTransport = ...
client = Client(timeout=httpx.Timeout(30.0), transport=transport)
```

```python
# v1
import httpx2
from lightkube import Client

transport: httpx2.BaseTransport = ...
client = Client(timeout=httpx2.Timeout(30.0), transport=transport)
```

For `AsyncClient`, use `httpx2.AsyncBaseTransport` for the transport instead.

Update exception handlers separately:

```python
# v0
import httpx

try:
    ...
except httpx.HTTPError:
    ...
```

```python
# v1
import httpx2

try:
    ...
except httpx2.HTTPError:
    ...
```

Alternatively, you can alias `httpx2` as `httpx` to reduce the number of code
changes:

```python
import httpx2 as httpx
```

If your application uses `httpx` for another dependency, keep that dependency
as needed, but use `httpx2` for objects and exceptions exchanged with
Lightkube.

## Models use msgspec.Struct

Lightkube's generated models now use
[msgspec.Struct](https://msgspec.dev/structs) instead of
standard-library dataclasses. Normal use of generated models is unchanged:
construct them, access their attributes, and use `from_dict` and `to_dict` as
before.

The benefit is that msgspec provides schema-aware, optimized encoding and
decoding with low allocation overhead. It can convert directly between bytes
and typed Struct instances, avoiding the intermediate standard Python object
representation. This is faster and more memory efficient while retaining
typed model fields.

In the benchmark of a 700-pod response, v1 decodes a Pod list into fully
materialized typed objects about 12x faster than v0 with `lazy=False`. It is
also about 2.2x faster than the v0 `lazy=True` measurement, although lazy
decoding deferred part of the conversion work until fields were accessed.

### Custom resources

In preparation for the msgspec migration, the `lightkube.core.schema`
compatibility layer has been available since Lightkube v0.15.1. Its use is
required for custom resource models from v1 onward, so make this source change
when upgrading. You can also apply it before upgrading.

Change:

```python
# v0.*
from dataclasses import dataclass, field
from lightkube.core.dataclasses_dict import DataclassDictMixIn
```

to:

```python
# v1.*
from lightkube.core.schema import dataclass, field, DictMixin
```

Models need to subclass `DictMixin` instead of `DataclassDictMixIn`, as shown in
the [custom resources guide](custom-resources.md). The `dataclass` decorator is
provided for source compatibility, but it is now a no-op. The `field` helper
translates dataclass-style field metadata for msgspec.

If your code imports `DataclassDictMixIn` or other helpers directly from
`lightkube.core.dataclasses_dict`, migrate those imports to the corresponding
exports from `lightkube.core.schema`. The `dataclasses_dict` implementation is
replaced by the msgspec-backed compatibility layer in v1.

## Remove lazy decoding and custom dict factories

`msgspec` decodes Structs eagerly, so lazy model decoding is no longer
available. The `lazy` argument is retained for compatibility in some APIs,
but it has no effect. In particular, passing `lazy=True` to
`DictMixin.from_dict` emits a `DeprecationWarning`; use the default eager
decoding instead and remove `lazy` arguments from your code.

The non-default `dict_factory` argument to `DictMixin.to_dict` is also
deprecated. Call `to_dict()` to receive a normal `dict`, then transform that
dictionary separately if a custom mapping type is required.

## Pod logs with follow

`Client.log` and `AsyncClient.log` now disable the HTTP read timeout when
`follow=True`. This allows a long-lived log stream to remain open while the
container is temporarily quiet. The configured timeout still applies to the
other timeout phases and to non-following log requests.

No call-site change is required, but code that expected an idle followed log
stream to fail with a read-timeout exception should now close or cancel the
stream explicitly.

## Recovering watches after a 410 response

When `Client.watch` or `AsyncClient.watch` is configured to retry, a Kubernetes
`410 Gone` response means that the saved `resourceVersion` is too old. v1
clears that version before retrying the request. Kubernetes can then return a
fresh state and the watch can continue instead of retrying forever with the
same invalid version.

The default error handler still raises errors. Opt into retry as before:

```python
from lightkube import Client
from lightkube.resources.core_v1 import Pod
from lightkube.types import on_error_retry

with Client() as client:
    for event, pod in client.watch(Pod, on_error=on_error_retry):
        print(event, pod.metadata.name)
```

Custom handlers that return `OnErrorAction.RETRY` receive the same 410
recovery behavior.

## Upgrade checklist

1. Change Lightkube-related `httpx` imports and exception handlers to
   `httpx2`, or use `import httpx2 as httpx`.
2. Change custom resource models to import `dataclass`, `field` and `DictMixin` from
   `lightkube.core.schema`.
3. Remove reliance on lazy decoding and non-default `dict_factory` values.
4. Review followed log streams and watch retry handlers if their previous
    failure behavior was part of your application logic.