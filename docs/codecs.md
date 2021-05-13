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
    or [generic resources](generic-resources.md) manually defined.

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
