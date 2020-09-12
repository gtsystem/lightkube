from typing import NamedTuple, List, Optional
from dataclasses import dataclass
import enum


class ResourceDef(NamedTuple):
    group: str
    version: str
    kind: str


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


class PatchType(enum.Enum):
    JSON = 'application/json-patch+json'
    MERGE = 'application/merge-patch+json'
    STRATEGIC = 'application/strategic-merge-patch+json'


class WatchOnError(enum.Enum):
    RETRY = 0
    STOP = 1
    RAISE = 2
