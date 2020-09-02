# Selectors

The methods `Client.list` and `Client.watch` allows to filter results on server side using
the attributes `labels` and `fields`.

See related [Kubernetes documentation](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/).

## Label Selectors

The attribute `labels` allows to filter object by labels.

The easier way to filter objects is to use the normal python dict syntax as follow: 

```python
# get objects having a label with key `env` and value `prod`
labels={"env": "prod"}
```

The dictionary can have multiple keys, this will result in multiple required matches:

```python
# get objects having labels env=prod AND app=myapp
labels={"env": "prod", "app": "myapp"}
```
