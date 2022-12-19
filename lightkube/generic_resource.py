from typing import Type, Any, Optional, overload

from .core import resource as res
from .core.client import Client
from .core.async_client import AsyncClient
from .core.internal_models import meta_v1, autoscaling_v1
from .core.internal_resources import apiextensions


__all__ = [
    'async_load_in_cluster_generic_resources',
    'create_global_resource',
    'create_namespaced_resource',
    'create_resources_from_crd',
    'get_generic_resource',
    'load_in_cluster_generic_resources',
]

_created_resources = {}


def get_generic_resource(version, kind):
    """Query generic resources already defined using one of the other methods described in this module or via
    `codecs.load_all_yaml(..., create_resources_for_crds=True)`

    **Parameters**

    * **version** `str` - Resource version including the API group. Example `stable.example.com/v1`
    * **kind** `str` - Resource kind. Example: `CronTab`

    **returns** class representing the generic resource or `None` if it's not found
    """
    global _created_resources
    model = _created_resources.get((version, kind))
    return model[0] if model is not None else None


class Generic(dict):
    @overload
    def __init__(self, apiVersion: str=None, kind: str=None,
                 metadata: meta_v1.ObjectMeta=None, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def apiVersion(self) -> str:
        return self.get('apiVersion')

    @property
    def kind(self) -> str:
        return self.get('kind')

    @property
    def status(self) -> str:
        return self.get('status')

    @property
    def metadata(self) -> Optional[meta_v1.ObjectMeta]:
        meta = self.get('metadata')
        if meta is None:
            return None
        elif isinstance(meta, meta_v1.ObjectMeta):
            return meta
        return meta_v1.ObjectMeta.from_dict(meta)

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(f"{item} not found")
        return self.get(item)

    @classmethod
    def from_dict(cls, d: dict, lazy=True):
        return cls(d)

    def to_dict(self, dict_factory=dict):
        d = dict_factory(self)
        if 'metadata' in d and isinstance(d['metadata'], meta_v1.ObjectMeta):
            d['metadata'] = d['metadata'].to_dict(dict_factory)
        return d


def create_api_info(group, version, kind, plural, verbs=None) -> res.ApiInfo:
    if verbs is None:
        verbs = ['delete', 'deletecollection', 'get', 'global_list', 'global_watch', 'list', 'patch',
               'post', 'put', 'watch']
    return res.ApiInfo(
        resource=res.ResourceDef(group, version, kind),
        plural=plural,
        verbs=verbs
    )


class GenericGlobalScale(res.GlobalSubResource, autoscaling_v1.Scale):
    pass


class GenericGlobalStatus(res.GlobalSubResource, Generic):
    pass


class GenericNamespacedScale(res.NamespacedResourceG, autoscaling_v1.Scale):
    pass


class GenericNamespacedStatus(res.NamespacedResourceG, Generic):
    pass


def _create_subresource(main_class, parent_info: res.ApiInfo, action):
    class TmpName(main_class):
        _api_info = res.ApiInfo(
            resource=parent_info.resource if action == 'status' else res.ResourceDef('autoscaling', 'v1', 'Scale'),
            parent=parent_info.resource,
            plural=parent_info.plural,
            verbs=['get', 'patch', 'put'],
            action=action,
        )

    TmpName.__name__ = TmpName.__qualname__ = f"{parent_info.resource.kind}{action.capitalize()}"
    return TmpName


class GenericGlobalResource(res.GlobalResource, Generic):
    Scale: Type[GenericGlobalScale]
    Status: Type[GenericGlobalStatus]


class GenericNamespacedResource(res.NamespacedResourceG, Generic):
    Scale: Type[GenericNamespacedScale]
    Status: Type[GenericNamespacedStatus]


def _create_resource(namespaced, group, version, kind, plural, verbs=None) -> Any:
    global _created_resources
    res_key = (f'{group}/{version}', kind)
    signature = (namespaced, plural, tuple(verbs) if verbs else None)
    if res_key in _created_resources:
        model, curr_signature = _created_resources[res_key]
        if curr_signature != signature:
            raise ValueError(f"Resource {kind} already created but with different signature")
        return model

    if namespaced:
        main, status, scale = GenericNamespacedResource, GenericNamespacedStatus, GenericNamespacedScale
    else:
        main, status, scale = GenericGlobalResource, GenericGlobalStatus, GenericGlobalScale

    class TmpName(main):
        _api_info = create_api_info(group, version, kind, plural, verbs=verbs)

        Scale = _create_subresource(scale, _api_info, action='scale')
        Status = _create_subresource(status, _api_info, action='status')

    TmpName.__name__ = TmpName.__qualname__ = kind
    _created_resources[res_key] = (TmpName, signature)
    return TmpName


def create_global_resource(group: str, version: str, kind: str, plural: str, verbs=None) \
        -> Type[GenericGlobalResource]:
    """Create a new class representing a global resource with the provided specifications.

    **Parameters**

    * **group** `str` - API group of the resource. Example `stable.example.com`.
    * **version** `str` - API group version. Example `v1`.
    * **kind** `str` - Resource name. Example `Job`.
    * **plural** `str` - Resource collection name. Example `jobs`.

    **returns**  Subclass of `GenericGlobalResource`.
    """
    return _create_resource(
        False, group, version, kind, plural, verbs=verbs)


def create_namespaced_resource(group: str, version: str, kind: str, plural: str, verbs=None) \
        -> Type[GenericNamespacedResource]:
    """Create a new class representing a namespaced resource with the provided specifications.

    **Parameters**

    * **group** `str` - API group of the resource. Example `stable.example.com`.
    * **version** `str` - API group version. Example `v1`.
    * **kind** `str` - Resource name. Example `Job`.
    * **plural** `str` - Resource collection name. Example `jobs`.

    **returns**  Subclass of `GenericNamespacedResource`.
    """
    return _create_resource(
        True, group, version, kind, plural, verbs=verbs)


def load_in_cluster_generic_resources(client: Client):
    """Loads all in-cluster CustomResourceDefinitions as generic resources.

    Once loaded, generic resources can be obtained from `generic_resource.get_generic_resource()`,
    or used implicitly such as when using `codecs.load_all_yaml()`.

    **Parameters**

    * **client** `Client` - Lightkube Client to use to load the CRDs.
    """
    crds = client.list(apiextensions.CustomResourceDefinition)
    for crd in crds:
        create_resources_from_crd(crd)


async def async_load_in_cluster_generic_resources(client: AsyncClient):
    """Loads all in-cluster CustomResourceDefinitions as generic resources.

    Once loaded, generic resources can be obtained from `generic_resource.get_generic_resource()`,
    or used implicitly such as when using `codecs.load_all_yaml()`.

    **Parameters**

    * **client** `AsyncClient` - Lightkube AsyncClient to use to load the CRDs.
    """
    crds = client.list(apiextensions.CustomResourceDefinition)
    async for crd in crds:
        create_resources_from_crd(crd)


def create_resources_from_crd(crd: apiextensions.CustomResourceDefinition):
    """Creates a generic resource for each version in a CustomResourceDefinition."""
    if crd.spec.scope == "Namespaced":
        creator = create_namespaced_resource
    elif crd.spec.scope == "Cluster":
        creator = create_global_resource
    else:
        raise ValueError(
            f"Unexpected scope for resource.  Expected 'Namespaced' or 'Cluster',"
            f" got {crd.spec.scope}"
        )

    for version in crd.spec.versions:
        creator(**_crd_to_dict(crd, version.name))


def _crd_to_dict(crd, version_name):
    return {
        "group": crd.spec.group,
        "version": version_name,
        "kind": crd.spec.names.kind,
        "plural": crd.spec.names.plural,
    }
