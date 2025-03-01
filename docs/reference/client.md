::: lightkube.Client

## `namespace` parameter

All API calls for namespaced resources will need to refer to a specific namespace.
By default the namespace provided in the kubeconfig file is used. This default
can be overridden when instantiating the client class with a different value.
You can also specify a specific namespace for a single call using the `namespace` parameter.

The methods `create` or `replace` will use the namespace defined in the object when it's present.
Notice that if the object namespace and the method's `namespace` parameter are set, 
both must have the same value.

Override rules summary:

* `client.method(..., namespace=..)`
* [`obj.metadata.namespace`] (Only when calling `create` or `replace`)
* `Client(..., namespace=...)`
* kubernetes config file

## List or watch objects in all namespaces

The methods `list` and `watch` can also return objects for all namespaces using `namespace='*'`.

