from typing import Union, TextIO, Iterator, List, Mapping

import yaml

from .generic_resource import GenericGlobalResource, GenericNamespacedResource, create_resources_from_crd
from .core.exceptions import LoadResourceError
from .core.resource_registry import resource_registry

__all__ = [
    'from_dict',
    'load_all_yaml',
    'dump_all_yaml',
    'resource_registry'
]

try:
    import jinja2
except ImportError:
    jinja2 = None

REQUIRED_ATTR = ('apiVersion', 'kind')

AnyResource = Union[GenericGlobalResource, GenericNamespacedResource]


def from_dict(d: dict) -> AnyResource:
    """Converts a kubernetes resource defined as python dict to the corresponding resource object.
    If the dict represent a standard resource, the function will automatically load the appropriate
    resource type. Generic resources are also supported and used assuming they were defined prior to
    the function call. Returns the resource object or raise a `LoadResourceError`.

    **parameters**

    * **d** - A dictionary representing a Kubernetes resource. Keys `apiVersion` and `kind` are
      always required.
    """
    if not isinstance(d, Mapping):
        raise LoadResourceError(f"Invalid resource definition, not a dict.")
    for attr in REQUIRED_ATTR:
        if attr not in d:
            raise LoadResourceError(f"Invalid resource definition, key '{attr}' missing.")

    model = resource_registry.load(d['apiVersion'], d['kind'])
    return model.from_dict(d)


def load_all_yaml(stream: Union[str, TextIO], context: dict = None, template_env = None, create_resources_for_crds: bool = False) -> List[AnyResource]:
    """Load kubernetes resource objects defined as YAML. See `from_dict` regarding how resource types are detected.
    Returns a list of resource objects or raise a `LoadResourceError`.  Skips any empty YAML documents in the
    stream, returning an empty list if all YAML documents are empty. Deep parse any items from .*List resources.

    **parameters**

    * **stream** - A file-like object or a string representing a yaml file or a template resulting in
        a yaml file.
    * **context** - When is not `None` the stream is considered a `jinja2` template and the `context`
        will be used during templating.
    * **template_env** - `jinja2` template environment to be used for templating. When absent a standard
        environment is used.
    * **create_resources_for_crds** - If True, a generic resource will be created for every version
        of every CRD found that does not already have a generic resource.  There will be no side
        effect for any CRD that already has a generic resource.  Else if False, no generic resources
         will be created.  Default is False.

    **NOTE**: When using the template functionality (setting the context parameter), the dependency
        module `jinja2` need to be installed.
    """
    if context is not None:
        stream = _template(stream, context=context, template_env=template_env)

    def _flatten(objects: Iterator) -> List[AnyResource]:
        """Flatten resources which have a kind = *List."""
        resources = []
        for obj in objects:
            if obj is None:
                continue
            if isinstance(obj, Mapping) and obj.get("kind", "").endswith("List"):
                resources += _flatten(obj.get("items") or [])
            else:
                res = from_dict(obj)
                resources.append(res)

                if create_resources_for_crds is True and res.kind == "CustomResourceDefinition":
                    create_resources_from_crd(res)
        return resources

    return _flatten(yaml.safe_load_all(stream))


def dump_all_yaml(resources: List[AnyResource], stream: TextIO = None, indent=2):
    """Write kubernetes resource objects as YAML into an open file.

    **parameters**

    * **resources** - List of resources to write on the file
    * **stream** - Path to a file where to write the resources. When not set the content is returned
      as a string.
    * **indent** - Number of characters for indenting nasted blocks.
    """
    res = [r.to_dict() for r in resources]
    return yaml.safe_dump_all(res, stream, indent=indent)


def _template(stream: Union[str, TextIO], context: dict = None, template_env = None) -> List[AnyResource]:
    """
    Template a stream using jinja2 and the given context
    """
    if jinja2 is None:
        raise ImportError("load_from_template requires jinja2 to be installed")

    if template_env is None:
        template_env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    elif not isinstance(template_env, jinja2.Environment):
        raise LoadResourceError("template_env is not a valid jinja2 template")

    tmpl = template_env.from_string(stream if isinstance(stream, str) else stream.read())
    return tmpl.render(**context)
