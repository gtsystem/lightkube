import importlib
from typing import Union, Type, Optional

from lightkube.core import resource as res
from lightkube.core.exceptions import LoadResourceError

AnyResource = Union[res.NamespacedResource, res.GlobalResource]

def _load_internal_resource(version, kind):
    if "/" in version:
        group, version_n = version.split("/")
        # Generic resource not defined, but it could be a k8s resource
        if group.endswith(".k8s.io"):
            group = group[:-7]
        group = group.replace(".", "_")
        module_name = "_".join([group, version_n])
    else:
        module_name = f'core_{version}'

    module = importlib.import_module(f'lightkube.resources.{module_name.lower()}')
    try:
        return getattr(module, kind)
    except AttributeError:
        raise LoadResourceError(f"Cannot find resource kind '{kind}' in module {module.__name__}")

def _maybe_internal(version):
    if "/" not in version:
        return True

    group = version.split("/")[0]
    # internal resources don't have namespace or end in .k8s.io
    return group.endswith(".k8s.io") or "." not in group


class ResourceRegistry:
    """Resource Registry used to load standard resources or to register custom resources
    """
    _registry: dict

    def __init__(self):
        self._registry = {}

    def register(self, resource: Type[AnyResource]) -> Type[AnyResource]:
        """Register a custom resource

        **parameters**

        * **resource** - Resource class to register.

        **returns** The `resource` class provided
        """
        info = resource._api_info
        version = f'{info.resource.group}/{info.resource.version}' if info.resource.group else info.resource.version
        res_key = (version, info.resource.kind)

        if res_key in self._registry:
            registered_resource = self._registry[res_key]
            if registered_resource is resource:   # already present
                return registered_resource
            raise ValueError(f"Another class for resource '{info.resource.kind}' is already registered")

        self._registry[res_key] = resource
        return resource

    def clear(self):
        """Clear the registry from all registered resources
        """
        self._registry.clear()

    def get(self, version: str, kind: str) -> Optional[Type[AnyResource]]:
        """Get a resource from the registry matching the given `version` and `kind`.

        **parameters**

        * **version** - Version of the resource as defined in the kubernetes definition. Example `example.com/v1`
        * **kind** - Resource kind. Example `CronJob`

        **returns** A `resource` class or `None` if there is no match in the registry.
        """
        return self._registry.get((version, kind))

    def load(self, version, kind) -> Optional[Type[AnyResource]]:
        """Load a standard resource from `lightkube.resources` given `version` and `kind`.
        This method look up the registry first and import the resource from the module only if it's not available there.

        * **version** - Version of the resource as defined in the kubernetes definition. Example `apps/v1`
        * **kind** - Resource kind. Example `Pod`

        **returns** A `resource` class if the resource is found. Otherwise an exception is raised
        """
        # check if this resource is in the registry
        resource = self.get(version, kind)
        if resource is not None:
            return resource

        # if not, we attempt to load from lightkube.resources
        if _maybe_internal(version):
            try:
                return self.register(_load_internal_resource(version, kind))
            except ImportError:
                pass

        raise LoadResourceError(f"Cannot find resource {kind} of group {version}. "
                                "If using a CRD, ensure a generic resource is defined.")

resource_registry = ResourceRegistry()
