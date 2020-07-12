from typing import Type, Iterator, TypeVar, Union, overload, Any, Dict, Tuple, List, Callable
import enum
import dataclasses
from dataclasses import dataclass
import json
import httpx
from ..config.config import KubeConfig

from . import resource as r
from .generic_client import GenericClient, AllNamespaces, raise_exc

NamespacedResource = TypeVar('NamespacedResource', bound=r.NamespacedResource)
GlobalResource = TypeVar('GlobalResource', bound=r.GlobalResource)
GlobalSubResource = TypeVar('GlobalSubResource', bound=r.GlobalSubResource)
NamespacedResourceG = TypeVar('NamespacedResourceG', bound=r.NamespacedResourceG)
NamespacedSubResource = TypeVar('NamespacedSubResource', bound=r.NamespacedSubResource)
AllNamespacedResource = TypeVar('AllNamespacedResource', r.NamespacedResource, r.NamespacedSubResource)
Resource = TypeVar('Resource', bound=r.Resource)


class Client:
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
        return self._client.request("delete", res=res, name=name, namespace=namespace)

    @overload
    def deletecollection(self, res: Type[GlobalResource]) -> None:
        ...

    @overload
    def deletecollection(self, res: Type[NamespacedResource], *, namespace: str = None) -> None:
        ...

    def deletecollection(self, res, *, namespace: str = None):
        return self._client.request("deletecollection", res=res, namespace=namespace)

    @overload
    def get(self, res: Type[GlobalResource], name: str) -> GlobalResource:
        ...

    @overload
    def get(self, res: Type[AllNamespacedResource], name: str, *, namespace: str = None) -> AllNamespacedResource:
        ...

    def get(self, res, name, *, namespace=None):
        return self._client.request("get", res=res, name=name, namespace=namespace)

    @overload
    def list(self, res: Type[GlobalResource], *, name: str = None) -> Iterator[GlobalResource]:
        ...

    @overload
    def list(self, res: Type[NamespacedResourceG], *, namespace: AllNamespaces = None, name: str = None) -> \
            Iterator[NamespacedResourceG]:
        ...

    @overload
    def list(self, res: Type[NamespacedResource], *, namespace: str = None, name: str = None) -> \
            Iterator[NamespacedResource]:
        ...

    def list(self, res, *, name=None, namespace=None):
        return self._client.request("list", res=res, name=name, namespace=namespace)

    @overload
    def watch(self, res: Type[GlobalResource], *, name: str = None, server_timeout: int = None,
              resource_version: str = None, on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, GlobalResource]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResourceG], *, namespace: AllNamespaces = None, name: str = None,
              server_timeout: int = None, resource_version: str = None,
              on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, NamespacedResourceG]]:
        ...

    @overload
    def watch(self, res: Type[NamespacedResource], *, namespace: str = None, name: str = None,
              server_timeout: int = None, resource_version: str = None,
              on_error: Callable[[Exception], r.WatchOnError] = raise_exc) -> \
            Iterator[Tuple[str, NamespacedResource]]:
        ...

    def watch(self, res, *, namespace=None, name=None, server_timeout=None, resource_version=None, on_error=raise_exc):
        br = self._client.prepare_request("list", res=res, name=name, namespace=namespace, watch=True, params={
            'timeoutSeconds': server_timeout,
            'resourceVersion': resource_version
        })
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
        return self._client.request("put", name=name, namespace=namespace, obj=obj)



