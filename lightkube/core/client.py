from typing import Type, Iterator, TypeVar, Union, overload, Any, Dict, Tuple, List, Callable, Iterable
import enum
import dataclasses
from dataclasses import dataclass
import json
import httpx
from ..config.config import KubeConfig
from .. import operators
from ..core import resource as r
from .generic_client import GenericClient, raise_exc

NamespacedResource = TypeVar('NamespacedResource', bound=r.NamespacedResource)
GlobalResource = TypeVar('GlobalResource', bound=r.GlobalResource)
GlobalSubResource = TypeVar('GlobalSubResource', bound=r.GlobalSubResource)
NamespacedSubResource = TypeVar('NamespacedSubResource', bound=r.NamespacedSubResource)
AllNamespacedResource = TypeVar('AllNamespacedResource', r.NamespacedResource, r.NamespacedSubResource)
Resource = TypeVar('Resource', bound=r.Resource)
LabelSelector = Dict[str, Union[str, None, operators.Operator, Iterable]]
FieldSelector = Dict[str, Union[str, operators.BinaryOperator]]


class Client:
    """Creates a new lightkube client

    **parameters**

    * **config** - Instance of `KubeConfig`. When not set the configuration will be detected automatically with the
      following order: in cluster config, `KUBECONFIG` environment variable, `~/.kube/config` file.
    * **namespace** - Default namespace to use. This attribute is used in case namespaced resources are called without
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
        """Return the default namespace that will be used when a namespace has not been specified"""
        return self._client.namespace

    @overload
    def delete(self, res: Type[GlobalResource], name: str) -> None:
        ...

    @overload
    def delete(self, res: Type[NamespacedResource], name: str, *, namespace: str = None) -> None:
        ...

    def delete(self, res, name: str, *, namespace: str = None):
        """Delete an object

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of the object to delete.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return self._client.request("delete", res=res, name=name, namespace=namespace)

    @overload
    def deletecollection(self, res: Type[GlobalResource]) -> None:
        ...

    @overload
    def deletecollection(self, res: Type[NamespacedResource], *, namespace: str = None) -> None:
        ...

    def deletecollection(self, res, *, namespace: str = None):
        """Delete all objects of the given kind

        * **res** - Resource kind.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return self._client.request("deletecollection", res=res, namespace=namespace)

    @overload
    def get(self, res: Type[GlobalResource], name: str) -> GlobalResource:
        ...

    @overload
    def get(self, res: Type[AllNamespacedResource], name: str, *, namespace: str = None) -> AllNamespacedResource:
        ...

    def get(self, res, name, *, namespace=None):
        """Return an object

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of the object to fetch.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return self._client.request("get", res=res, name=name, namespace=namespace)

    @overload
    def list(self, res: Type[GlobalResource], *, chunk_size: int = None, labels: LabelSelector = None, fields: FieldSelector = None) -> \
            Iterator[GlobalResource]:
        ...

    @overload
    def list(self, res: Type[NamespacedResource], *, namespace: str = None, chunk_size: int = None,
             labels: LabelSelector = None, fields: FieldSelector = None) -> \
            Iterator[NamespacedResource]:
        ...

    def list(self, res, *, namespace=None, chunk_size=None, labels=None, fields=None):
        """Return an iterator of objects matching the selection criteria.

        **parameters**

        * **res** - resource kind.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **chunk_size** - *(optional)* Limit the amount of objects returned for each rest API call.
             This method will automatically execute all subsequent calls until no more data is available.
        * **labels** - *(optional)* Filter the returned objects by labels.
        * **fields** - *(optional)* Filter the returned objects by fields.
        """

        br = self._client.prepare_request(
            'list', res=res, namespace=namespace, labels=labels, fields=fields, params={'limit': chunk_size}
        )
        return self._client.list(br)

    @overload
    def watch(self, res: Type[GlobalResource], *, labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None,
              resource_version: str = None, on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, GlobalResource]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResource], *, namespace: str = None,
              labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None, resource_version: str = None,
              on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, NamespacedResource]]:
        ...

    def watch(self, res, *, namespace=None, labels=None, fields=None, server_timeout=None, resource_version=None, on_error=raise_exc):
        """Watch changes to objects

        **parameters**

        * **res** - resource kind.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **labels** - *(optional)* Filter the returned objects by labels.
        * **fields** - *(optional)* Filter the returned objects by fields.
        * **server_timeout** - *(optional)* Server side timeout to close a watch request. This method
            will automatically create a new request whenever the backend close the connection without errors.
        * **resource_version** - *(optional)* When set, only modification events following this version will be returned.
        * **on_error** - *(optional)* Function that will be called when an error occur. By default any error will raise
            an exception and stop the watching.
        """
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
    def patch(self, res: Type[AllNamespacedResource], name: str,
              obj: Union[AllNamespacedResource, Dict, List], *, namespace: str = None,
              patch_type: r.PatchType = r.PatchType.STRATEGIC) -> AllNamespacedResource:
        ...

    def patch(self, res, name, obj, *, namespace=None, patch_type=r.PatchType.STRATEGIC):
        """Patch an object.

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of the object to patch.
        * **obj** - patch object.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **patch_type** - *(optional)* Type of patch to execute. Default `PatchType.STRATEGIC`.
        """
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
        """Creates a new object

        * **obj** - object to create. This need to be an instance of a resource kind.
        * **name** - *(optional)* Required only for sub-resources: Name of the resource to which this object belongs.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
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
        """Replace an existing resource.

        * **obj** - new object. This need to be an instance of a resource kind.
        * **name** - *(optional)* Required only for sub-resources: Name of the resource to which this object belongs.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return self._client.request("put", name=name, namespace=namespace, obj=obj)



