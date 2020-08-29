import sys
from typing import Type, Iterator, TypeVar, Union, overload, Any, Dict, Callable
import dataclasses
from dataclasses import dataclass
import json
from copy import copy

import httpx

from . import resource as r
from ..config.config import KubeConfig
from ..config import client_adapter
from .internal_models import meta_v1
from .selector import build_selector


ALL_NS = '*'


class ApiError(httpx.HTTPStatusError):
    def __init__(
            self, request: httpx.Request = None, response: httpx.Response = None) -> None:
        self.status = meta_v1.Status.from_dict(response.json())
        super().__init__(self.status.message, request=request, response=response)


def transform_exception(e: httpx.HTTPError):
    if isinstance(e, httpx.HTTPStatusError) and e.response.headers['Content-Type'] == 'application/json':
        return ApiError(request=e.request, response=e.response)
    return e


def raise_exc(e):
    return r.WatchOnError.RAISE


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

    def get_request(self):
        br = self._br
        if self._version is not None:
            br.params['resourceVersion'] = self._version
        print(br)
        return self._build_request(br.method, br.url, params=br.params)

    def process_one_line(self, line):
        line = json.loads(line)
        tp = line['type']
        obj = line['object']
        self._version = obj['metadata']['resourceVersion']
        return tp, self._convert(obj, lazy=self._lazy)


class GenericClient:
    def __init__(self, config: KubeConfig = None, namespace: str = None, timeout: httpx.Timeout = None, lazy=True):
        if config is None:
            try:
                config = KubeConfig.from_service_account()
            except Exception:
                config = KubeConfig.from_file()
        if timeout is None:
            timeout = httpx.Timeout(10)
        self._config = config
        self._timeout = timeout
        self._watch_timeout = copy(timeout)
        self._watch_timeout.read_timeout = None
        self._lazy = lazy
        self._client = client_adapter.Client(config, timeout)
        self.namespace = namespace if namespace else config.namespace

    def prepare_request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None,
                        labels=None, fields=None,
                        watch: bool = False, patch_type: r.PatchType = r.PatchType.STRATEGIC, params: dict = None) -> BasicRequest:
        if params is not None:
            params = {k: v for k, v in params.items() if v is not None}
        else:
            params = {}
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

        if real_method not in res.api_info.verbs:
            if watch:
                raise ValueError(f"Resource '{res.__name__}' is not watchable")
            else:
                raise ValueError(f"method '{method}' not supported by resource '{res.__name__}'")

        if watch:
            params['watch'] = "true"

        if res.api_info.parent is None:
            base = res.api_info.resource
        else:
            base = res.api_info.parent

        if base.group == '':
            path = ["api", base.version]
        else:
            path = ["apis", base.group, base.version]

        if namespaced and namespace != ALL_NS:
            if namespace is None and method in ('post', 'put'):
                namespace = obj.metadata.namespace
            if namespace is None:
                namespace = self.namespace
            path.extend(["namespaces", namespace])

        if method in ('post', 'put', 'patch'):
            if obj is None:
                raise ValueError("obj is required for post, put or patch")

            if method == 'patch' and not isinstance(obj, r.Resource):
                data = obj
            else:
                data = obj.to_dict()

        path.append(res.api_info.plural)
        if method in ('delete', 'get', 'patch', 'put') or res.api_info.action:
            if name is None and method == 'put':
                name = obj.metadata.name
            if name is None:
                raise ValueError("resource name not defined")
            path.append(name)

        headers = None
        if method == 'patch':
            headers = {'Content-Type': patch_type.value}

        if res.api_info.action:
            path.append(res.api_info.action)

        http_method = METHOD_MAPPING[method]
        if http_method == 'DELETE':
            res = None

        if labels is not None:
            params['labelSelector'] = build_selector(labels)

        if fields is not None:
            params['fieldSelector'] = build_selector(fields, binaryOnly=True)

        return BasicRequest(method=http_method, url="/".join(path), params=params, response_type=res, data=data, headers=headers)

    def watch(self, br: BasicRequest, on_error: Callable[[Exception], r.WatchOnError] = raise_exc):
        wd = WatchDriver(br, self._client.build_request, self._lazy)
        while True:
            req = wd.get_request()
            resp = self._client.send(req, stream=True, timeout=self._watch_timeout)
            try:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    yield wd.process_one_line(line)
            except Exception as e:
                action = on_error(e)
                if action is r.WatchOnError.RAISE:
                    raise
                if action is r.WatchOnError.STOP:
                    break
                continue

    def handle_response(self, method, resp, br):
        try:
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise transform_exception(e)
        res = br.response_type
        if res is None:
            # TODO: delete/deletecollection actions normally return a Status object, we may want to return it as well
            return
        data = resp.json()
        if method == 'list':
            if 'metadata' in data and 'continue' in data['metadata']:
                cont = True
                br.params['continue'] = data['metadata']['continue']
            else:
                cont = False
            return cont, (res.from_dict(obj, lazy=self._lazy) for obj in data['items'])
        else:
            if res is not None:
                return res.from_dict(data, lazy=self._lazy)

    def request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None, labels=None, fields=None, watch: bool = False, patch_type: r.PatchType = r.PatchType.STRATEGIC) -> Any:
        br = self.prepare_request(method, res, obj, name, namespace, labels, fields, watch, patch_type)
        print(br)
        req = self._client.build_request(br.method, br.url, params=br.params, json=br.data, headers=br.headers)
        resp = self._client.send(req)
        return self.handle_response(method, resp, br)

    def list(self, br: BasicRequest) -> Any:
        cont = True
        while cont:
            print(br)
            req = self._client.build_request(br.method, br.url, params=br.params, json=br.data, headers=br.headers)
            resp = self._client.send(req)
            cont, chunk = self.handle_response('list', resp, br)
            yield from chunk
