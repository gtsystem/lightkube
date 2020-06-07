from typing import NamedTuple, List, Optional
from dataclasses import dataclass


class ResourceDef(NamedTuple):
    group: str
    version: str
    kind: str


@dataclass
class ApiInfo:
    resource: ResourceDef
    parent: Optional[ResourceDef]
    plural: str
    verbs: List[str]


class Resource:
    api_info: ApiInfo


class NamespacedResource(Resource):
    pass


class GlobalResource(Resource):
    pass


class NamespacedResourceG(NamespacedResource):
    pass



