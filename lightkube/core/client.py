from typing import Type, Iterator, TypeVar, Union, overload, Dict, Tuple, List, Iterable, AsyncIterable
import httpx
from ..config.kubeconfig import SingleConfig, KubeConfig
from .. import operators
from ..core import resource as r
from .generic_client import GenericSyncClient, GenericAsyncClient
from ..core.exceptions import ConditionError, ObjectDeleted
from ..types import OnErrorHandler, PatchType, on_error_raise
from .internal_resources import core_v1
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
    * **trust_env** - Ignore environment variables, also passed through to httpx.Client trust_env.  See its
      docs for further description. If False, empty config will be derived from_file(DEFAULT_KUBECONFIG)
    """
    def __init__(self, config: Union[SingleConfig, KubeConfig] = None, namespace: str = None,
                 timeout: httpx.Timeout = None, lazy=True, trust_env: bool = True):
        self._client = GenericSyncClient(config, namespace=namespace, timeout=timeout, lazy=lazy, trust_env=trust_env)

    @property
    def namespace(self):
        """Return the default namespace that will be used when a namespace has not been specified"""
        return self._client.namespace

    @property
    def config(self) -> SingleConfig:
        """Return the kubernetes configuration used in this client"""
        return self._client.config

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
    def wait(
        self,
        res: Type[GlobalResource],
        name: str,
        *,
        for_conditions: Iterable[str],
        raise_for_conditions: Iterable[str] = (),
    ) -> GlobalResource:
        ...

    @overload
    def wait(
        self,
        res: Type[AllNamespacedResource],
        name: str,
        *,
        for_conditions: Iterable[str],
        namespace: str = None,
        raise_for_conditions: Iterable[str] = (),
    ) -> AllNamespacedResource:
        ...

    def wait(
        self,
        res,
        name: str,
        *,
        for_conditions: Iterable[str],
        namespace=None,
        raise_for_conditions: Iterable[str] = (),
    ):
        """Waits for specified conditions.

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of resource to wait for.
        * **for_conditions** - Condition types that are considered a success and will end the wait.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **raise_for_conditions** - *(optional)* Condition types that are considered failures and will exit the wait early.
        """

        kind = r.api_info(res).plural
        full_name = f'{kind}/{name}'

        for_conditions = list(for_conditions)
        raise_for_conditions = list(raise_for_conditions)

        for op, obj in self.watch(res, namespace=namespace, fields={'metadata.name': name}):
            if obj.status is None:
                continue

            if op == "DELETED":
                raise ObjectDeleted(full_name)

            try:
                status = obj.status.to_dict()
            except AttributeError:
                status = obj.status

            conditions = [c for c in status.get('conditions', []) if c['status'] == 'True']
            if any(c['type'] in for_conditions for c in conditions):
                return obj

            failures = [c for c in conditions if c['type'] in raise_for_conditions]

            if failures:
                raise ConditionError(full_name, [f.get('message', f['type']) for f in failures])

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

    @overload
    def log(self, name:str, *, namespace: str = None, container: str = None, follow: bool = False,
            since: int = None, tail_lines: int = None, timestamps: bool = False) -> Iterator[str]:
        ...

    def log(self, name, *, namespace=None, container=None, follow=False,
            since=None, tail_lines=None, timestamps=False):
        """Return log lines for the given Pod

        **parameters**

        * **name** - Name of the Pod.
        * **namespace** - *(optional)* Name of the namespace containing the Pod.
        * **container** - *(optional)* The container for which to stream logs. Defaults to only container if there is one container in the pod.
        * **follow** - *(optional)* If `True`, follow the log stream of the pod.
        * **since** - *(optional)* If set, a relative time in seconds before the current time from which to fetch logs.
        * **tail_lines** - *(optional)* If set, the number of lines from the end of the logs to fetch.
        * **timestamps** - *(optional)* If `True`, add an RFC3339 or RFC3339Nano timestamp at the beginning of every line of log output.
        """
        br = self._client.prepare_request(
            'get', core_v1.PodLog, name=name, namespace=namespace,
            params={'timestamps': timestamps, 'tailLines': tail_lines, 'container': container,
                    'sinceSeconds': since, 'follow': follow})
        req = self._client.build_adapter_request(br)
        resp = self._client.send(req, stream=follow)
        self._client.raise_for_status(resp)
        return resp.iter_lines()


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
    * **trust_env** - Ignore environment variables, also passed through to httpx.AsyncClient trust_env.  See its
      docs for further description. If False, empty config will be derived from_file(DEFAULT_KUBECONFIG)
    """
    def __init__(self, config: Union[SingleConfig, KubeConfig] = None, namespace: str = None,
                 timeout: httpx.Timeout = None, lazy=True, trust_env: bool = True):
        self._client = GenericAsyncClient(config, namespace=namespace, timeout=timeout, lazy=lazy, trust_env=trust_env)

    @property
    def namespace(self):
        """Return the default namespace that will be used when a namespace has not been specified"""
        return self._client.namespace

    @property
    def config(self) -> SingleConfig:
        """Return the kubernetes configuration used in this client"""
        return self._client.config

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
    async def wait(
        self,
        res: Type[GlobalResource],
        name: str,
        *,
        for_conditions: Iterable[str],
        raise_for_conditions: Iterable[str] = (),
    ) -> GlobalResource:
        ...

    @overload
    async def wait(
        self,
        res: Type[AllNamespacedResource],
        name: str,
        *,
        for_conditions: Iterable[str],
        namespace: str = None,
        raise_for_conditions: Iterable[str] = (),
    ) -> AllNamespacedResource:
        ...

    async def wait(
        self,
        res,
        name: str,
        *,
        for_conditions: Iterable[str],
        namespace=None,
        raise_for_conditions: Iterable[str] = (),
    ):
        """Waits for specified conditions.

        **parameters**

        * **res** - Resource kind.
        * **name** - Name of resource to wait for.
        * **for_conditions** - Condition types that are considered a success and will end the wait.
        * **namespace** - *(optional)* Name of the namespace containing the object (Only for namespaced resources).
        * **raise_for_conditions** - *(optional)* Condition types that are considered failures and will exit the wait early.
        """

        kind = r.api_info(res).plural
        full_name = f'{kind}/{name}'

        for_conditions = list(for_conditions)
        raise_for_conditions = list(raise_for_conditions)

        async for op, obj in self.watch(res, namespace=namespace, fields={'metadata.name': name}):
            if obj.status is None:
                continue

            if op == "DELETED":
                raise ObjectDeleted(full_name)

            try:
                status = obj.status.to_dict()
            except AttributeError:
                status = obj.status

            conditions = [c for c in status.get('conditions', []) if c['status'] == 'True']
            if any(c['type'] in for_conditions for c in conditions):
                return obj

            failures = [c for c in conditions if c['type'] in raise_for_conditions]

            if failures:
                raise ConditionError(full_name, [f.get('message', f['type']) for f in failures])

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

    @overload
    def log(self, name:str, *, namespace: str = None, container: str = None, follow: bool = False,
            since: int = None, tail_lines: int = None, timestamps: bool = False) -> AsyncIterable[str]:
        ...

    def log(self, name, *, namespace=None, container=None, follow=False,
            since=None, tail_lines=None, timestamps=False):
        """Return log lines for the given Pod

        **parameters**

        * **name** - Name of the Pod.
        * **namespace** - *(optional)* Name of the namespace containing the Pod.
        * **container** - *(optional)* The container for which to stream logs. Defaults to only container if there is one container in the pod.
        * **follow** - *(optional)* If `True`, follow the log stream of the pod.
        * **since** - *(optional)* If set, a relative time in seconds before the current time from which to fetch logs.
        * **tail_lines** - *(optional)* If set, the number of lines from the end of the logs to fetch.
        * **timestamps** - *(optional)* If `True`, add an RFC3339 or RFC3339Nano timestamp at the beginning of every line of log output.
        """
        br = self._client.prepare_request(
            'get', core_v1.PodLog, name=name, namespace=namespace,
            params={'timestamps': timestamps, 'tailLines': tail_lines, 'container': container,
                    'sinceSeconds': since, 'follow': follow})
        req = self._client.build_adapter_request(br)

        async def stream_log():
            resp = await self._client.send(req, stream=follow)
            self._client.raise_for_status(resp)
            async for line in resp.aiter_lines():
                yield line
        return stream_log()

    async def close(self):
        """Close the underline httpx client"""
        await self._client.close()
