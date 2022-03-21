import time
from typing import Type, Any, Dict, Union
import dataclasses
from dataclasses import dataclass
import json
import asyncio

import httpx

from . import resource as r
from ..config.kubeconfig import KubeConfig, SingleConfig, DEFAULT_KUBECONFIG
from ..config import client_adapter
from .exceptions import ApiError
from .selector import build_selector
from ..types import OnErrorAction, OnErrorHandler, on_error_raise, PatchType


ALL_NS = '*'


def transform_exception(e: httpx.HTTPError):
    if isinstance(e, httpx.HTTPStatusError) and e.response.headers['Content-Type'] == 'application/json':
        return ApiError(request=e.request, response=e.response)
    return e


METHOD_MAPPING = {
    'delete': 'DELETE',
    'deletecollection': 'DELETE',
    'get': 'GET',
    'global_list': 'GET',
    'global_watch': 'GET',
    'list': 'GET',
    'patch': 'PATCH',
    'post': 'POST',
    'put': 'PUT',
    'watch': 'GET'
}

@dataclass
class BasicRequest:
    method: str
    url: str
    response_type: Any
    params: Dict[str, str] = dataclasses.field(default_factory=dict)
    data: Any = None
    headers: Dict[str, str] = None


class WatchDriver:
    def __init__(self, br: BasicRequest, build_request, lazy):
        self._version = br.params.get('resourceVersion')
        self._convert = br.response_type.from_dict
        self._br = br
        self._build_request = build_request
        self._lazy = lazy

    def get_request(self, timeout):
        br = self._br
        if self._version is not None:
            br.params['resourceVersion'] = self._version
        return self._build_request(br.method, br.url, params=br.params, timeout=timeout)

    def process_one_line(self, line):
        line = json.loads(line)
        tp = line['type']
        obj = line['object']
        self._version = obj['metadata']['resourceVersion']
        return tp, self._convert(obj, lazy=self._lazy)


class GenericClient:
    AdapterClient = staticmethod(client_adapter.Client)

    def __init__(self, config: Union[SingleConfig, KubeConfig] = None, namespace: str = None,
                 timeout: httpx.Timeout = None, lazy=True, trust_env: bool = True, field_manager: str = None):
        self._timeout = httpx.Timeout(10) if timeout is None else timeout
        self._watch_timeout = httpx.Timeout(self._timeout)
        self._watch_timeout.read = None
        self._lazy = lazy
        if config is None and trust_env:
            config = KubeConfig.from_env().get()
        elif config is None and not trust_env:
            config = KubeConfig.from_file(DEFAULT_KUBECONFIG).get()
        elif isinstance(config, KubeConfig):
            config = config.get()

        self.config = config
        self._client = self.AdapterClient(config, timeout, trust_env=trust_env)
        self._field_manager = field_manager
        self.namespace = namespace if namespace else config.namespace

    def prepare_request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None,
                        watch: bool = False, params: dict = None, headers: dict = None) -> BasicRequest:
        if params is not None:
            params = {k: v for k, v in params.items() if v is not None}
        else:
            params = {}
        if headers is not None:
            headers = {k: v for k, v in headers.items() if v is not None}
        data = None
        if res is None:
            if obj is None:
                raise ValueError("At least a resource or an instance of a resource need to be provided")
            res = obj.__class__

        namespaced = issubclass(res, (r.NamespacedResource, r.NamespacedSubResource))

        if namespace == ALL_NS:
            if not issubclass(res, r.NamespacedResourceG):
                raise ValueError(f"Class {res} doesn't support global {method}")
            if method not in ('list', 'watch'):
                raise ValueError("Only methods 'list' and 'watch' can be called for all namespaces")
            real_method = "global_watch" if watch else "global_" + method
        else:
            real_method = "watch" if watch else method

        api_info = r.api_info(res)
        if real_method not in api_info.verbs:
            if watch:
                raise ValueError(f"Resource '{res.__name__}' is not watchable")
            else:
                raise ValueError(f"method '{method}' not supported by resource '{res.__name__}'")

        if watch:
            params['watch'] = "true"

        if api_info.parent is None:
            base = api_info.resource
        else:
            base = api_info.parent

        if base.group == '':
            path = ["api", base.version]
        else:
            path = ["apis", base.group, base.version]

        if namespaced and namespace != ALL_NS:
            if method in ('post', 'put') and obj.metadata.namespace is not None:
                if namespace is None:
                    namespace = obj.metadata.namespace
                elif namespace != obj.metadata.namespace:
                    raise ValueError(f"The namespace value '{namespace}' differ from the "
                                     f"namespace in the object metadata '{obj.metadata.namespace}'")
            if namespace is None:
                namespace = self.namespace
            path.extend(["namespaces", namespace])

        if method in ('post', 'put', 'patch'):
            if self._field_manager is not None and 'fieldManager' not in params:
                params['fieldManager'] = self._field_manager
            if method == 'patch' and headers['Content-Type'] == PatchType.APPLY.value and 'fieldManager' not in params:
                raise ValueError('Parameter "field_manager" is required for PatchType.APPLY')
            if obj is None:
                raise ValueError("obj is required for post, put or patch")

            if method == 'patch' and not isinstance(obj, r.Resource):
                data = obj
            else:
                data = obj.to_dict()
                # The following block, ensures that apiVersion and kind are always set.
                # this is needed as k8s fails if this data are not provided for objects derived by CRDs (Issue #27)
                if 'apiVersion' not in data:
                    data['apiVersion'] = api_info.resource.api_version
                if 'kind' not in data:
                    data['kind'] = api_info.resource.kind

        path.append(api_info.plural)
        if method in ('delete', 'get', 'patch', 'put') or api_info.action:
            if name is None and method == 'put':
                name = obj.metadata.name
            if name is None:
                raise ValueError("resource name not defined")
            path.append(name)

        if api_info.action:
            path.append(api_info.action)

        http_method = METHOD_MAPPING[method]
        if http_method == 'DELETE':
            res = None

        return BasicRequest(method=http_method, url="/".join(path), params=params, response_type=res, data=data, headers=headers)

    @staticmethod
    def raise_for_status(resp):
        try:
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise transform_exception(e)

    def build_adapter_request(self, br: BasicRequest):
        return self._client.build_request(br.method, br.url, params=br.params, json=br.data, headers=br.headers)

    def handle_response(self, method, resp, br):
        self.raise_for_status(resp)
        res = br.response_type
        if res is None:
            # TODO: delete/deletecollection actions normally return a Status object, we may want to return it as well
            return
        data = resp.json()
        if method == 'list':
            if 'metadata' in data and data['metadata'].get('continue'):
                cont = True
                br.params['continue'] = data['metadata']['continue']
            else:
                cont = False
            return cont, (res.from_dict(obj, lazy=self._lazy) for obj in data['items'])
        else:
            if res is not None:
                return res.from_dict(data, lazy=self._lazy)


class GenericSyncClient(GenericClient):
    def send(self, req, stream=False):
        return self._client.send(req, stream=stream)

    def watch(self, br: BasicRequest, on_error: OnErrorHandler = on_error_raise):
        wd = WatchDriver(br, self._client.build_request, self._lazy)
        err_count = 0
        while True:
            req = wd.get_request(timeout=self._watch_timeout)
            resp = self.send(req, stream=True)
            try:
                resp.raise_for_status()
                err_count = 0
                for line in resp.iter_lines():
                    yield wd.process_one_line(line)
            except Exception as e:
                err_count += 1
                handle_error = on_error(e, err_count)
                if handle_error.action is OnErrorAction.RAISE:
                    raise
                if handle_error.action is OnErrorAction.STOP:
                    break
                if handle_error.sleep > 0:
                    time.sleep(handle_error.sleep)
                continue

    def request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None, watch: bool = False,
                headers: dict = None, params: dict = None) -> Any:
        br = self.prepare_request(method, res, obj, name, namespace, watch, headers=headers, params=params)
        req = self.build_adapter_request(br)
        resp = self.send(req)
        return self.handle_response(method, resp, br)

    def list(self, br: BasicRequest) -> Any:
        cont = True
        while cont:
            req = self.build_adapter_request(br)
            resp = self.send(req)
            cont, chunk = self.handle_response('list', resp, br)
            yield from chunk


class GenericAsyncClient(GenericClient):
    AdapterClient = staticmethod(client_adapter.AsyncClient)

    async def send(self, req, stream=False):
        return await self._client.send(req, stream=stream)

    async def watch(self, br: BasicRequest, on_error: OnErrorHandler = on_error_raise):
        wd = WatchDriver(br, self._client.build_request, self._lazy)
        err_count = 0
        while True:
            req = wd.get_request(timeout=self._watch_timeout)
            resp = await self.send(req, stream=True)
            try:
                resp.raise_for_status()
                err_count = 0
                async for line in resp.aiter_lines():
                    yield wd.process_one_line(line)
            except Exception as e:
                err_count += 1
                handle_error = on_error(e, err_count)
                if handle_error.action is OnErrorAction.RAISE:
                    raise
                if handle_error.action is OnErrorAction.STOP:
                    break
                if handle_error.sleep > 0:
                    await asyncio.sleep(handle_error.sleep)
                continue
            finally:
                await resp.aclose()

    async def request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None,
                      watch: bool = False, headers: dict = None, params: dict = None) -> Any:
        br = self.prepare_request(method, res, obj, name, namespace, watch, headers=headers, params=params)
        req = self.build_adapter_request(br)
        resp = await self.send(req)
        return self.handle_response(method, resp, br)

    async def list(self, br: BasicRequest) -> Any:
        cont = True
        while cont:
            req = self.build_adapter_request(br)
            resp = await self.send(req)
            cont, chunk = self.handle_response('list', resp, br)
            for item in chunk:
                yield item

    async def close(self):
        await self._client.aclose()
