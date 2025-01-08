# List-Watch pattern

As documented in [section "Efficient detection of
changes"](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes)
in kubernetes reference, we can use the `resourceVersion` from a list
response in a subsequent watch request, to reliably receive changes
since the list operation.  In lightkube this information is available
on the object returned from `list()`:

```python
seen_pods = {}
async for pod in (podlist := client.list(Pod)):
    seen_pods[pod.metadata.name] = pod
async for event, pod in client.watch(Pod, resource_version=podlist.resourceVersion):
    match event:
        case "ADDED" | "MODIFIED":
            seen_pods[pod.metadata.name] = pod
        case "DELETED":
            del seen_pods[pod.metadata.name]
```

Note that the field `resourceVersion` is only available after
iteration started, and will raise `lightkube.NotReadyError` if it is
accessed before iterating the result.
