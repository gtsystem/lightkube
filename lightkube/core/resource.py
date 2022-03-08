from typing import NamedTuple, List, Optional
from dataclasses import dataclass


class ResourceDef(NamedTuple):
    group: str
    version: str
    kind: str

    @property
    def api_version(self):
        return f"{self.group}/{self.version}" if self.group else self.version


@dataclass
class ApiInfo:
    resource: ResourceDef
    plural: str
    verbs: List[str]
    parent: Optional[ResourceDef] = None
    action: str = None


class Resource:
    _api_info: ApiInfo


def api_info(res: Resource):
    return res._api_info


class NamespacedResource(Resource):
    pass


class NamespacedSubResource(Resource):
    pass


class GlobalResource(Resource):
    pass


class NamespacedResourceG(NamespacedResource):
    pass


class GlobalSubResource(Resource):
    pass
