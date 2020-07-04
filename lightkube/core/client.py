from typing import Type, Iterator, TypeVar, Union, overload, Any, Dict, Tuple, List
import enum
import dataclasses
from dataclasses import dataclass
import json
import httpx
from ..config.config import KubeConfig

from . import resource as r
from .generic_client import GenericClient

NamespacedResource = TypeVar('NamespacedResource', bound=r.NamespacedResource)
GlobalResource = TypeVar('GlobalResource', bound=r.GlobalResource)
GlobalSubResource = TypeVar('GlobalSubResource', bound=r.GlobalSubResource)
NamespacedResourceG = TypeVar('NamespacedResourceG', bound=r.NamespacedResourceG)
NamespacedSubResource = TypeVar('NamespacedSubResource', bound=r.NamespacedSubResource)
AllNamespacedResource = TypeVar('AllNamespacedResource', r.NamespacedResource, r.NamespacedSubResource)
Resource = TypeVar('Resource', bound=r.Resource)


class Client:
    def __init__(self, config: KubeConfig = None, timeout: httpx.Timeout = None, lazy=True):
        self._client = GenericClient(config, timeout=timeout, lazy=lazy)
        self._namespace_client = NamespacedClient(self._client)

    @property
    def namespaced(self):
        return self._namespace_client

    @property
    def ns(self):
        return self._namespace_client

    def delete(self, res: Type[GlobalResource], name: str) -> None:
        return self._client.request("delete", res=res, name=name)

    def deletecollection(self, res: Type[GlobalResource]) -> None:
        return self._client.request("deletecollection", res=res)

    def get(self, res: Type[GlobalResource], name: str) -> GlobalResource:
        return self._client.request("get", res=res, name=name)

    @overload
    def list(self, res: Type[GlobalResource], *, name: str = None) -> Iterator[GlobalResource]:
        ...

    @overload
    def list(self, res: Type[NamespacedResourceG], *, name: str = None) -> Iterator[NamespacedResourceG]:
        ...

    def list(self, res, *, name=None):
        return self._client.request("list", res=res, name=name)

    @overload
    def watch(self, res: Type[GlobalResource], *, name: str = None) -> Iterator[Tuple[str, GlobalResource]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResourceG], *, name: str = None) -> Iterator[Tuple[str, NamespacedResourceG]]:
        ...

    def watch(self, res, *, name=None, watch=False):
        return self._client.request("list", res=res, name=name, watch=True)

    @overload
    def patch(self, res: Type[GlobalSubResource], name: str, obj: Union[GlobalSubResource, Dict, List], patch_type: r.PatchType) -> GlobalSubResource:
        ...

    @overload
    def patch(self, res: Type[GlobalResource], name: str, obj: Union[GlobalResource, Dict, List], patch_type: r.PatchType) -> GlobalResource:
        ...

    def patch(self, res, name, obj):
        return self._client.request("patch", res=res, name=name, obj=obj, patch_type=r.PatchType.STRATEGIC)

    @overload
    def post(self, obj: GlobalSubResource,  name: str) -> GlobalSubResource:
        ...

    @overload
    def post(self, obj: GlobalResource) -> GlobalResource:
        ...

    def post(self, obj, name=None):
        return self._client.request("post", name=name, obj=obj)

    @overload
    def put(self, obj: GlobalSubResource, name: str) -> GlobalSubResource:
        ...

    @overload
    def put(self, obj: GlobalResource) -> GlobalResource:
        ...

    def put(self, obj, name=None):
        return self._client.request("put", name=name, obj=obj)


class NamespacedClient:
    def __init__(self, client: GenericClient = None):
        if not client:
            client = GenericClient()
        self._client = client

    def delete(self, res: Type[NamespacedResource], name: str, namespace: str) -> None:
        return self._client.request("delete", res=res, name=name, namespace=namespace, namespaced=True)

    def deletecollection(self, res: Type[NamespacedResource], namespace: str) -> None:
        return self._client.request("deletecollection", res=res, namespace=namespace, namespaced=True)

    def get(self, res: Type[AllNamespacedResource], name: str, namespace: str) -> AllNamespacedResource:
        return self._client.request("get", res=res, name=name, namespace=namespace, namespaced=True)

    def list(self, res: Type[NamespacedResource], namespace: str, *, name: str = None) -> Iterator[NamespacedResource]:
        return self._client.request("list", res=res, namespace=namespace, name=name, namespaced=True)

    def watch(self, res: Type[NamespacedResource], namespace: str, *, name: str = None) -> Iterator[Tuple[str, NamespacedResource]]:
        return self._client.request("list", res=res, namespace=namespace, name=name, watch=True, namespaced=True)

    @overload
    def patch(self, res: Type[NamespacedSubResource], name: str, namespace: str, obj: Union[NamespacedSubResource, Dict, List], patch_type: r.PatchType) -> NamespacedSubResource:
        ...

    @overload
    def patch(self, res: Type[NamespacedResource], name: str, namespace: str, obj: Union[NamespacedResource, Dict, List], patch_type: r.PatchType) -> NamespacedResource:
        ...

    def patch(self, res, name: str, namespace: str, obj: object, patch_type=r.PatchType.STRATEGIC):
        return self._client.request("patch", res=res, name=name, namespace=namespace, obj=obj, namespaced=True, patch_type=patch_type)

    @overload
    def post(self, obj: NamespacedSubResource, name: str, namespace: str) -> NamespacedSubResource:
        ...

    @overload
    def post(self, obj: NamespacedResource) -> NamespacedResource:
        ...

    def post(self, obj, name=None, namespace=None):
        return self._client.request("post", name=name, namespace=namespace, obj=obj, namespaced=True)

    @overload
    def put(self, obj: NamespacedSubResource, name: str, namespace: str) -> NamespacedSubResource:
        ...

    @overload
    def put(self, obj: NamespacedResource) -> NamespacedResource:
        ...

    def put(self, obj, name=None, namespace=None):
        return self._client.request("put", name=name, namespace=namespace, obj=obj, namespaced=True)


