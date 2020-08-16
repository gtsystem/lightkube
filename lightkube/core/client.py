from typing import Type, Iterator, TypeVar, Union, overload, Any, Dict, Tuple, List, Callable, Iterable
import enum
import dataclasses
from dataclasses import dataclass
import json
import httpx
from ..config.config import KubeConfig
from .. import operators
from . import resource as r
from .generic_client import GenericClient, AllNamespaces, raise_exc

NamespacedResource = TypeVar('NamespacedResource', bound=r.NamespacedResource)
GlobalResource = TypeVar('GlobalResource', bound=r.GlobalResource)
GlobalSubResource = TypeVar('GlobalSubResource', bound=r.GlobalSubResource)
NamespacedResourceG = TypeVar('NamespacedResourceG', bound=r.NamespacedResourceG)
NamespacedSubResource = TypeVar('NamespacedSubResource', bound=r.NamespacedSubResource)
AllNamespacedResource = TypeVar('AllNamespacedResource', r.NamespacedResource, r.NamespacedSubResource)
Resource = TypeVar('Resource', bound=r.Resource)
LabelSelector = Dict[str, Union[str, None, operators.Operator, Iterable]]
FieldSelector = Dict[str, Union[str, operators.BinaryOperator]]


class Client:
    """Creates a new lightkube client

    **parameters**

    * **config** - instance of `KubeConfig`. When not set the configuration will be detected automatically with the
      following order: in cluster config, `KUBECONFIG` environment variable, `~/.kube/config` file.
    * **namespace** - default namespace to use. This attribute is used in case namespaced resources are called without
      defining a namespace. If not specified, the default namespace set in your kube configuration will be used.
    * **timeout** - Instance of `httpx.Timeout`. By default all timeouts are set to 10 seconds. Notice that read timeout
      is ignored when watching changes.
    * **lazy** - When set, the returned objects will be decoded from the JSON payload in a lazy way, i.e. only when
      accessed.
    """
    def __init__(self, config: KubeConfig = None, namespace: str = None, timeout: httpx.Timeout = None, lazy=True):
        self._client = GenericClient(config, namespace=namespace, timeout=timeout, lazy=lazy)

    @property
    def namespace(self):
        """Returns the default namespace that will be used when a namespace has not been specified"""
        return self._client.namespace

    @overload
    def delete(self, res: Type[GlobalResource], name: str) -> None:
        ...

    @overload
    def delete(self, res: Type[NamespacedResource], name: str, *, namespace: str = None) -> None:
        ...

    def delete(self, res, name: str, *, namespace: str = None):
        """Deletes the object named `name` of kind `res`."""
        return self._client.request("delete", res=res, name=name, namespace=namespace)

    @overload
    def deletecollection(self, res: Type[GlobalResource]) -> None:
        ...

    @overload
    def deletecollection(self, res: Type[NamespacedResource], *, namespace: str = None) -> None:
        ...

    def deletecollection(self, res, *, namespace: str = None):
        """Deletes all objects of kind `res`."""
        return self._client.request("deletecollection", res=res, namespace=namespace)

    @overload
    def get(self, res: Type[GlobalResource], name: str) -> GlobalResource:
        ...

    @overload
    def get(self, res: Type[AllNamespacedResource], name: str, *, namespace: str = None) -> AllNamespacedResource:
        ...

    def get(self, res, name, *, namespace=None):
        """Returns the object named `name` of kind `res`."""
        return self._client.request("get", res=res, name=name, namespace=namespace)

    @overload
    def list(self, res: Type[GlobalResource], *, labels: LabelSelector = None, fields: FieldSelector = None) -> \
            Iterator[GlobalResource]:
        ...

    @overload
    def list(self, res: Type[NamespacedResourceG], *, namespace: AllNamespaces = None,
             labels: LabelSelector = None, fields: FieldSelector = None) -> \
            Iterator[NamespacedResourceG]:
        ...

    @overload
    def list(self, res: Type[NamespacedResource], *, namespace: str = None,
             labels: LabelSelector = None, fields: FieldSelector = None) -> \
            Iterator[NamespacedResource]:
        ...

    def list(self, res, *, namespace=None, labels=None, fields=None):
        """Returns a list objects of kind `res`. You can filter the returned items by `labels` or `fields`"""
        return self._client.request("list", res=res, namespace=namespace, labels=labels, fields=fields)

    @overload
    def watch(self, res: Type[GlobalResource], *, labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None,
              resource_version: str = None, on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, GlobalResource]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResourceG], *, namespace: AllNamespaces = None,
              labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None, resource_version: str = None,
              on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, NamespacedResourceG]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResource], *, namespace: str = None,
              labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None, resource_version: str = None,
              on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, NamespacedResource]]:
        ...

    def watch(self, res, *, namespace=None, labels=None, fields=None, server_timeout=None, resource_version=None, on_error=raise_exc):
        """Watch objects of kind `res`. You can filter the returned items by `labels` or `fields`"""
        br = self._client.prepare_request("list", res=res, namespace=namespace, labels=labels,
            fields=fields, watch=True,
            params={'timeoutSeconds': server_timeout, 'resourceVersion': resource_version}
        )
        return self._client.watch(br, on_error=on_error)

    @overload
    def patch(self, res: Type[GlobalSubResource], name: str,
              obj: Union[GlobalSubResource, Dict, List], *,
              patch_type: r.PatchType = r.PatchType.STRATEGIC) -> GlobalSubResource:
        ...

    @overload
    def patch(self, res: Type[GlobalResource], name: str,
              obj: Union[GlobalResource, Dict, List], *,
              patch_type: r.PatchType = r.PatchType.STRATEGIC) -> GlobalResource:
        ...

    @overload
    def patch(self, res: Type[NamespacedSubResource], name: str,
              obj: Union[NamespacedSubResource, Dict, List], *, namespace: str = None,
              patch_type: r.PatchType = r.PatchType.STRATEGIC) -> NamespacedSubResource:
        ...

    @overload
    def patch(self, res: Type[NamespacedResource], name: str,
              obj: Union[NamespacedResource, Dict, List], *, namespace: str = None,
              patch_type: r.PatchType = r.PatchType.STRATEGIC) -> NamespacedResource:
        ...

    def patch(self, res, name, obj, *, namespace=None, patch_type=r.PatchType.STRATEGIC):
        """Patch the object named `name` of kind `res` with the content of `obj`."""
        return self._client.request("patch", res=res, name=name, namespace=namespace, obj=obj, patch_type=patch_type)

    @overload
    def create(self, obj: GlobalSubResource,  name: str) -> GlobalSubResource:
        ...

    @overload
    def create(self, obj: NamespacedSubResource, name: str, *, namespace: str = None) -> NamespacedSubResource:
        ...

    @overload
    def create(self, obj: GlobalResource) -> GlobalResource:
        ...

    @overload
    def create(self, obj: NamespacedResource) -> NamespacedResource:
        ...

    def create(self, obj, name=None, *, namespace=None):
        """Creates a new object `obj`. If `obj` is a sub-resources, the `name` of the object should be provided."""
        return self._client.request("post", name=name, namespace=namespace, obj=obj)

    @overload
    def replace(self, obj: GlobalSubResource, name: str) -> GlobalSubResource:
        ...

    @overload
    def replace(self, obj: NamespacedSubResource, name: str, *, namespace: str = None) -> NamespacedSubResource:
        ...

    @overload
    def replace(self, obj: GlobalResource) -> GlobalResource:
        ...

    @overload
    def replace(self, obj: NamespacedResource) -> NamespacedResource:
        ...

    def replace(self, obj, name=None, *, namespace=None):
        """Replace an existing resource with `obj`. If `obj` is a sub-resources, the `name` of the object
        should be provided."""
        return self._client.request("put", name=name, namespace=namespace, obj=obj)



