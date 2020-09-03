# Selectors

The methods `Client.list` and `Client.watch` allows to filter results on server side
using the attributes `labels` and `fields`.


## Label Selectors

The attribute `labels` represents a set of requirements computed against the object labels
that need to be satisfied in order for an object to be matched.
The parameter value is as a dictionary where key represent a label key 
and the value represent a matching operation.

This is equivalent to use the Kubernetes API parameters `labelSelector`.
For more details regarding label selectors see the official [Kubernetes documentation](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels).

This is the list of possible matching operations:

| Operation | Operator | Example | Alternative syntax |
|---|---|---|---|
| Equal | `equal(value)` | `{"env": equal("prod")}` | `{"env": "prod"}` |
| Not equal | `not_equal(value)` | `{"env": not_equal("prod")}` | - |
| Exists | `exists()` | `{"env": exists()}` | `{"env": None}` |
| Not exists | `not_exists()` | `{"env": not_exists()}` | - |
| In | `in_(sequence)` | `{"env": in_(["prod", "dev"])}` | `{"env": ["prod", "dev"]}` |
| Not in | `not_in(sequence)` | `{"env": not_in(["prod", "dev"])}` | - |

### Examples

Match objects having a label with key `env` and value `prod`:
```python
labels={"env": "prod"}
```

Match objects having `env == prod` and `app == myapp`:
```python
labels={"env": "prod", "app": "myapp"}
```

Match objects having `env == prod` and a label with key `app`:
```python
labels={"env": "prod", "app": None}
```

Match objects having `env == prod` or `env == dev`:
```python
labels={"env": ("prod", "dev")}
```

The following example uses the operators functions:

```python
from lightkube import operators as op
```

Match objects not having a label key `app`:
```python
labels={"app": op.not_exists()}
```

Match objects where `env != prod`:
```python
labels={"env": op.not_equal("prod")}
```

Match objects where `env != prod and env != dev`:
```python
labels={"env": op.not_in(["prod", "dev"])}
```

## Field Selectors

The attribute `fields` let you select Kubernetes resources based on the value of 
one or more resource fields. This is equivalent to use the Kubernetes API parameters `fieldSelector`.
For more details regarding field selectors see the official [Kubernetes documentation](https://kubernetes.io/docs/concepts/overview/working-with-objects/field-selectors).

!!! note
    Each resource support a specific (and very limited) set of fields that can be used in the selector.

!!! note
    The valid operations for field selectors are only "equal" and "not equal".

### Examples

Match objects where the name is `myobj`:
```python
fields={"metadata.name": "myobj"}
```

Match objects where status phase is "Pending":
```python
fields={"status.phase": "Pending"}
```

Match objects if they are not in the "default" namespace:
```python
fields={"metadata.namespace": op.not_equal("default")}
```
