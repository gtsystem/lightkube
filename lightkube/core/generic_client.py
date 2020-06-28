from typing import Type, Iterator, TypeVar, Union, overload, Any, Dict, Tuple
import dataclasses
from dataclasses import dataclass
import json
from copy import copy

import httpx

from . import resource as r
from ..config.config import KubeConfig
from ..config import client_adapter


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


class GenericClient:
    def __init__(self, config: KubeConfig = None, timeout: httpx.Timeout = None):
        if config is None:
            try:
                config = KubeConfig.from_service_account()
            except Exception:
                config = KubeConfig.from_file()
        if timeout is None:
            timeout = httpx.Timeout()
        self._config = config
        self._timeout = timeout
        self._client = client_adapter.Client(config, timeout)

    def prepare_request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None, watch: bool = False) -> BasicRequest:
        params = {}
        if res is None:
            if obj is None:
                raise ValueError("At least a resource or an instance of a resource need to be provided")
            res = obj.__class__

        if namespace is None and issubclass(res, r.NamespacedResourceG):
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

        if namespace and issubclass(res, (r.NamespacedResource, r.NamespacedSubResource)):
            path.extend(["namespaces", namespace])
        path.append(res.api_info.plural)
        if method in ('delete', 'get', 'patch', 'put') or res.api_info.action:
            path.append(name)
        if res.api_info.action:
            path.append(res.api_info.action)

        http_method = METHOD_MAPPING[method]
        return BasicRequest(method=http_method, url="/".join(path), params=params, response_type=res)

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
                for l in resp.iter_lines():
                    l = json.loads(l)
                    tp = l['type']
                    obj = l['object']
                    version = obj['metadata']['resourceVersion']
                    yield tp, res.from_dict(obj)
            except httpx.HTTPError:     # TODO: see if there is any better exception to catch here
                continue

    def request(self, method, res: Type[r.Resource] = None, obj=None, name=None, namespace=None, watch: bool = False) -> Any:
        br = self.prepare_request(method, res, obj, name, namespace, watch)
        if watch:
            return self.watch(br)
        req = self._client.build_request(br.method, br.url, params=br.params)
        resp = self._client.send(req).json()
        res = br.response_type
        if method == 'list':
            return (res.from_dict(obj) for obj in resp['items'])
        else:
            return res.from_dict(resp)
