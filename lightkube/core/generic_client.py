from typing import Type, Iterator, TypeVar, Union, overload, Any, Dict, Tuple
import dataclasses
from dataclasses import dataclass
import json
from copy import copy

import httpx

from . import resource as r
from ..config.config import KubeConfig
from ..config import client_adapter
from ..models import meta_v1


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


class GenericClient:
    def __init__(self, config: KubeConfig = None, timeout: httpx.Timeout = None, lazy=True):
        if config is None:
            try:
                config = KubeConfig.from_service_account()
            except Exception:
                config = KubeConfig.from_file()
        if timeout is None:
            timeout = httpx.Timeout()
        self._config = config
        self._timeout = timeout
        self._lazy = lazy
        self._client = client_adapter.Client(config, timeout)

    def prepare_request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None, namespaced=False, watch: bool = False, patch_type: r.PatchType = r.PatchType.STRATEGIC) -> BasicRequest:
        params = {}
        data = None
        if res is None:
            if obj is None:
                raise ValueError("At least a resource or an instance of a resource need to be provided")
            res = obj.__class__

        if not namespaced and issubclass(res, r.NamespacedResourceG) and method in ('list', 'watch'):
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

        #namespaced = issubclass(res, (r.NamespacedResource, r.NamespacedSubResource))
        if namespaced:
            if namespace is None and method in ('post', 'put'):
                namespace = obj.metadata.namespace
            if namespace is None:
                raise ValueError("resource namespace not defined")
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
        if method == 'delete':
            res = None

        return BasicRequest(method=http_method, url="/".join(path), params=params, response_type=res, data=data, headers=headers)

    def watch(self, br: BasicRequest):
        timeout = copy(self._timeout)
        timeout.read_timeout = None
        version = br.params.get('resourceVersion')
        res = br.response_type
        while True:
            if version is not None:
                br.params['resourceVersion'] = version
            req = self._client.build_request(br.method, br.url, params=br.params)
            resp = self._client.send(req, stream=True, timeout=timeout)
            try:
                resp.raise_for_status()
                for l in resp.iter_lines():
                    l = json.loads(l)
                    tp = l['type']
                    obj = l['object']
                    version = obj['metadata']['resourceVersion']
                    yield tp, res.from_dict(obj, lazy=self._lazy)
            except httpx.HTTPError:
                # TODO: see if there is any better exception to catch here
                # TODO: wait in case of some errors or fail in case of others
                continue

    def request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None, namespaced=False, watch: bool = False, patch_type: r.PatchType = r.PatchType.STRATEGIC) -> Any:
        br = self.prepare_request(method, res, obj, name, namespace, namespaced, watch, patch_type)
        print(br)
        if watch:
            return self.watch(br)
        req = self._client.build_request(br.method, br.url, params=br.params, json=br.data, headers=br.headers)
        resp = self._client.send(req)
        resp.raise_for_status()
        data = resp.json()
        res = br.response_type
        if method == 'list':
            return (res.from_dict(obj, lazy=self._lazy) for obj in data['items'])
        else:
            if res is not None:
                return res.from_dict(data, lazy=self._lazy)
