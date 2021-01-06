from typing import Type, Iterator, TypeVar, Union, overload, Dict, Tuple, List, Iterable, AsyncIterable
import httpx
from ..config.kubeconfig import SingleConfig, KubeConfig
from .. import operators
from ..core import resource as r
from .generic_client import GenericSyncClient, GenericAsyncClient
from ..types import OnErrorHandler, PatchType, on_error_raise
from .selector import build_selector

NamespacedResource = TypeVar('NamespacedResource', bound=r.NamespacedResource)
GlobalResource = TypeVar('GlobalResource', bound=r.GlobalResource)
GlobalSubResource = TypeVar('GlobalSubResource', bound=r.GlobalSubResource)
NamespacedSubResource = TypeVar('NamespacedSubResource', bound=r.NamespacedSubResource)
AllNamespacedResource = TypeVar('AllNamespacedResource', r.NamespacedResource, r.NamespacedSubResource)
Resource = TypeVar('Resource', bound=r.Resource)
LabelValue = Union[str, None, operators.Operator, Iterable]
FieldValue = Union[str, operators.BinaryOperator, operators.SequenceOperator]
LabelSelector = Dict[str, LabelValue]
FieldSelector = Dict[str, FieldValue]


class Client:
    """Creates a new lightkube client

    **parameters**

    * **config** - Instance of `SingleConfig` or `KubeConfig`. When not set the configuration will be detected automatically
      using the following order: in-cluster config, `KUBECONFIG` environment variable, `~/.kube/config` file.
    * **namespace** - Default namespace to use. This attribute is used in case namespaced resources are called without
      defining a namespace. If not specified, the default namespace set in your kube configuration will be used.
    * **timeout** - Instance of `httpx.Timeout`. By default all timeouts are set to 10 seconds. Notice that read timeout
      is ignored when watching changes.
    * **lazy** - When set, the returned objects will be decoded from the JSON payload in a lazy way, i.e. only when
      accessed.
    """
    def __init__(self, config: Union[SingleConfig, KubeConfig] = None, namespace: str = None, timeout: httpx.Timeout = None, lazy=True):
        self._client = GenericSyncClient(config, namespace=namespace, timeout=timeout, lazy=lazy)

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
        * **labels** - *(optional)* Limit the returned objects by labels. More [details](../selectors).
        * **fields** - *(optional)* Limit the returned objects by fields. More [details](../selectors).
        """

        br = self._client.prepare_request(
            'list', res=res, namespace=namespace,
            params={
                'limit': chunk_size,
                'labelSelector': build_selector(labels) if labels else None,
                'fieldSelector': build_selector(fields, for_fields=True) if fields else None
            }
        )
        return self._client.list(br)

    @overload
    def watch(self, res: Type[GlobalResource], *, labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None,
              resource_version: str = None, on_error: OnErrorHandler = on_error_raise) -> \
            Iterator[Tuple[str, GlobalResource]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResource], *, namespace: str = None,
              labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None, resource_version: str = None,
              on_error: OnErrorHandler = on_error_raise) -> \
            Iterator[Tuple[str, NamespacedResource]]:
        ...

    def watch(self, res, *, namespace=None, labels=None, fields=None, server_timeout=None, resource_version=None, on_error=on_error_raise):
        """Watch changes to objects

        **parameters**

        * **res** - resource kind.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **labels** - *(optional)* Limit the returned objects by labels. More [details](../selectors).
        * **fields** - *(optional)* Limit the returned objects by fields. More [details](../selectors).
        * **server_timeout** - *(optional)* Server side timeout in seconds to close a watch request.
            This method will automatically create a new request whenever the backend close the connection
            without errors.
        * **resource_version** - *(optional)* When set, only modification events following this version will be returned.
        * **on_error** - *(optional)* Function that control what to do in case of errors.
            The default implementation will raise any error.
        """
        br = self._client.prepare_request("list", res=res, namespace=namespace, watch=True,
            params={
                'timeoutSeconds': server_timeout,
                'resourceVersion': resource_version,
                'labelSelector': build_selector(labels) if labels else None,
                'fieldSelector': build_selector(fields, for_fields=True) if fields else None
            }
        )
        return self._client.watch(br, on_error=on_error)

    @overload
    def patch(self, res: Type[GlobalSubResource], name: str,
              obj: Union[GlobalSubResource, Dict, List], *,
              patch_type: PatchType = PatchType.STRATEGIC) -> GlobalSubResource:
        ...

    @overload
    def patch(self, res: Type[GlobalResource], name: str,
              obj: Union[GlobalResource, Dict, List], *,
              patch_type: PatchType = PatchType.STRATEGIC) -> GlobalResource:
        ...

    @overload
    def patch(self, res: Type[AllNamespacedResource], name: str,
              obj: Union[AllNamespacedResource, Dict, List], *, namespace: str = None,
              patch_type: PatchType = PatchType.STRATEGIC) -> AllNamespacedResource:
        ...

    def patch(self, res, name, obj, *, namespace=None, patch_type=PatchType.STRATEGIC):
        """Patch an object.

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of the object to patch.
        * **obj** - patch object.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **patch_type** - *(optional)* Type of patch to execute. Default `PatchType.STRATEGIC`.
        """
        return self._client.request("patch", res=res, name=name, namespace=namespace, obj=obj,
                                    headers={'Content-Type': patch_type.value})

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

        **parameters**

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

        **parameters**

        * **obj** - new object. This need to be an instance of a resource kind.
        * **name** - *(optional)* Required only for sub-resources: Name of the resource to which this object belongs.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return self._client.request("put", name=name, namespace=namespace, obj=obj)


class AsyncClient:
    """Creates a new lightkube client

    **parameters**

    * **config** - Instance of `SingleConfig` or `KubeConfig`. When not set the configuration will be detected automatically
      using the following order: in-cluster config, `KUBECONFIG` environment variable, `~/.kube/config` file.
    * **namespace** - Default namespace to use. This attribute is used in case namespaced resources are called without
      defining a namespace. If not specified, the default namespace set in your kube configuration will be used.
    * **timeout** - Instance of `httpx.Timeout`. By default all timeouts are set to 10 seconds. Notice that read timeout
      is ignored when watching changes.
    * **lazy** - When set, the returned objects will be decoded from the JSON payload in a lazy way, i.e. only when
      accessed.
    """
    def __init__(self, config: Union[SingleConfig, KubeConfig] = None, namespace: str = None, timeout: httpx.Timeout = None, lazy=True):
        self._client = GenericAsyncClient(config, namespace=namespace, timeout=timeout, lazy=lazy)

    @property
    def namespace(self):
        """Return the default namespace that will be used when a namespace has not been specified"""
        return self._client.namespace

    @overload
    async def delete(self, res: Type[GlobalResource], name: str) -> None:
        ...

    @overload
    async def delete(self, res: Type[NamespacedResource], name: str, *, namespace: str = None) -> None:
        ...

    async def delete(self, res, name: str, *, namespace: str = None):
        """Delete an object

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of the object to delete.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return await self._client.request("delete", res=res, name=name, namespace=namespace)

    @overload
    async def deletecollection(self, res: Type[GlobalResource]) -> None:
        ...

    @overload
    async def deletecollection(self, res: Type[NamespacedResource], *, namespace: str = None) -> None:
        ...

    async def deletecollection(self, res, *, namespace: str = None):
        """Delete all objects of the given kind

        * **res** - Resource kind.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return await self._client.request("deletecollection", res=res, namespace=namespace)

    @overload
    async def get(self, res: Type[GlobalResource], name: str) -> GlobalResource:
        ...

    @overload
    async def get(self, res: Type[AllNamespacedResource], name: str, *, namespace: str = None) -> AllNamespacedResource:
        ...

    async def get(self, res, name, *, namespace=None):
        """Return an object

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of the object to fetch.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return await self._client.request("get", res=res, name=name, namespace=namespace)

    @overload
    def list(self, res: Type[GlobalResource], *, chunk_size: int = None, labels: LabelSelector = None, fields: FieldSelector = None) -> \
            AsyncIterable[GlobalResource]:
        ...

    @overload
    def list(self, res: Type[NamespacedResource], *, namespace: str = None, chunk_size: int = None,
             labels: LabelSelector = None, fields: FieldSelector = None) -> \
            AsyncIterable[NamespacedResource]:
        ...

    def list(self, res, *, namespace=None, chunk_size=None, labels=None, fields=None):
        """Return an iterator of objects matching the selection criteria.

        **parameters**

        * **res** - resource kind.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **chunk_size** - *(optional)* Limit the amount of objects returned for each rest API call.
             This method will automatically execute all subsequent calls until no more data is available.
        * **labels** - *(optional)* Limit the returned objects by labels. More [details](../selectors).
        * **fields** - *(optional)* Limit the returned objects by fields. More [details](../selectors).
        """

        br = self._client.prepare_request(
            'list', res=res, namespace=namespace,
            params={
                'limit': chunk_size,
                'labelSelector': build_selector(labels) if labels else None,
                'fieldSelector': build_selector(fields, for_fields=True) if fields else None
            }
        )
        return self._client.list(br)

    @overload
    def watch(self, res: Type[GlobalResource], *, labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None,
              resource_version: str = None, on_error: OnErrorHandler = on_error_raise) -> \
            AsyncIterable[Tuple[str, GlobalResource]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResource], *, namespace: str = None,
              labels: LabelSelector = None, fields: FieldSelector = None,
              server_timeout: int = None, resource_version: str = None,
              on_error: OnErrorHandler = on_error_raise) -> \
            AsyncIterable[Tuple[str, NamespacedResource]]:
        ...

    def watch(self, res, *, namespace=None, labels=None, fields=None, server_timeout=None, resource_version=None, on_error=on_error_raise):
        """Watch changes to objects

        **parameters**

        * **res** - resource kind.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **labels** - *(optional)* Limit the returned objects by labels. More [details](../selectors).
        * **fields** - *(optional)* Limit the returned objects by fields. More [details](../selectors).
        * **server_timeout** - *(optional)* Server side timeout in seconds to close a watch request.
            This method will automatically create a new request whenever the backend close the connection
            without errors.
        * **resource_version** - *(optional)* When set, only modification events following this version will be returned.
        * **on_error** - *(optional)* Function that control what to do in case of errors.
            The default implementation will raise any error.
        """
        br = self._client.prepare_request("list", res=res, namespace=namespace, watch=True,
            params={
                'timeoutSeconds': server_timeout,
                'resourceVersion': resource_version,
                'labelSelector': build_selector(labels) if labels else None,
                'fieldSelector': build_selector(fields, for_fields=True) if fields else None
            }
        )
        return self._client.watch(br, on_error=on_error)

    @overload
    async def patch(self, res: Type[GlobalSubResource], name: str,
              obj: Union[GlobalSubResource, Dict, List], *,
              patch_type: PatchType = PatchType.STRATEGIC) -> GlobalSubResource:
        ...

    @overload
    async def patch(self, res: Type[GlobalResource], name: str,
              obj: Union[GlobalResource, Dict, List], *,
              patch_type: PatchType = PatchType.STRATEGIC) -> GlobalResource:
        ...

    @overload
    async def patch(self, res: Type[AllNamespacedResource], name: str,
              obj: Union[AllNamespacedResource, Dict, List], *, namespace: str = None,
              patch_type: PatchType = PatchType.STRATEGIC) -> AllNamespacedResource:
        ...

    async def patch(self, res, name, obj, *, namespace=None, patch_type=PatchType.STRATEGIC):
        """Patch an object.

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of the object to patch.
        * **obj** - patch object.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **patch_type** - *(optional)* Type of patch to execute. Default `PatchType.STRATEGIC`.
        """
        return await self._client.request("patch", res=res, name=name, namespace=namespace, obj=obj,
                                          headers={'Content-Type': patch_type.value})

    @overload
    async def create(self, obj: GlobalSubResource,  name: str) -> GlobalSubResource:
        ...

    @overload
    async def create(self, obj: NamespacedSubResource, name: str, *, namespace: str = None) -> NamespacedSubResource:
        ...

    @overload
    async def create(self, obj: GlobalResource) -> GlobalResource:
        ...

    @overload
    async def create(self, obj: NamespacedResource) -> NamespacedResource:
        ...

    async def create(self, obj, name=None, *, namespace=None):
        """Creates a new object

        **parameters**

        * **obj** - object to create. This need to be an instance of a resource kind.
        * **name** - *(optional)* Required only for sub-resources: Name of the resource to which this object belongs.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return await self._client.request("post", name=name, namespace=namespace, obj=obj)

    @overload
    async def replace(self, obj: GlobalSubResource, name: str) -> GlobalSubResource:
        ...

    @overload
    async def replace(self, obj: NamespacedSubResource, name: str, *, namespace: str = None) -> NamespacedSubResource:
        ...

    @overload
    async def replace(self, obj: GlobalResource) -> GlobalResource:
        ...

    @overload
    async def replace(self, obj: NamespacedResource) -> NamespacedResource:
        ...

    async def replace(self, obj, name=None, *, namespace=None):
        """Replace an existing resource.

        **parameters**

        * **obj** - new object. This need to be an instance of a resource kind.
        * **name** - *(optional)* Required only for sub-resources: Name of the resource to which this object belongs.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        """
        return await self._client.request("put", name=name, namespace=namespace, obj=obj)

    async def close(self):
        """Close the underline httpx client"""
        await self._client.close()
