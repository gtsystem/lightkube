from typing import Type, Iterator, TypeVar, Union, overload
from .resource import NamespacedResourceG, GlobalResource, NamespacedResource

NSR = TypeVar('NamespacedResource', bound=NamespacedResource)
GR = TypeVar('GlobalResource', bound=GlobalResource)
GLR = TypeVar('NamespacedResourceG', bound=NamespacedResourceG)


class Client:
    def __init__(self):
        pass

    def delete(self, res: Type[GR], name: str) -> None:
        pass

    def deletecollection(self, res: Type[GR]) -> None:
        pass

    def get(self, res: Type[GR], name: str) -> GR:
        pass

    @overload
    def list(self, res: Type[GR], watch: bool=False) -> Iterator[GR]:
        pass

    @overload
    def list(self, res: Type[GLR], watch: bool=False) -> Iterator[GLR]:
        pass

    def list(self, res, watch=False):
        pass

    def patch(self, res: Type[GR], patch: object) -> GR:
        pass

    def post(self, res: GR) -> GR:
        pass

    def put(self, res: GR) -> GR:
        pass

    def watch(self, res: Type[GR], name: str) -> Iterator[GR]:
        pass


class NamespacedClient:
    def __init__(self):
        pass

    def delete(self, res: Type[NSR], name: str, namespace: str) -> None:
        pass

    def deletecollection(self, res: Type[NSR], namespace: str) -> None:
        pass

    def get(self, res: Type[NSR], name: str, namespace: str) -> NSR:
        pass

    def list(self, res: Type[NSR], namespace: str, watch: bool=False) -> Iterator[NSR]:
        pass

    def patch(self, res: Type[NSR], namespace: str, patch: object) -> NSR:
        pass

    def post(self, res: NSR) -> NSR:
        pass

    def put(self, res: NSR) -> NSR:
        pass

    def watch(self, res: Type[NSR], name: str) -> Iterator[NSR]:
        pass


