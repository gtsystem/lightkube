import importlib
from typing import Union, TextIO, List

import yaml

from . import Client
from .generic_resource import get_generic_resource, GenericGlobalResource, GenericNamespacedResource, \
    create_namespaced_resource, create_global_resource
from .core.exceptions import LoadResourceError
from .resources.apiextensions_v1 import CustomResourceDefinition

try:
    import jinja2
except ImportError:
    jinja2 = None

REQUIRED_ATTR = ('apiVersion', 'kind')

AnyResource = Union[GenericGlobalResource, GenericNamespacedResource]


def _load_model(version, kind, client=None):
    if "/" in version:
        group, version_n = version.split("/")
        # Check if a generic resource was defined
        model = get_generic_resource(version, kind)
        if model is not None:
            return model

        # Generic resource not defined, but it could be a k8s resource
        if group.endswith(".k8s.io"):
            group = group[:-7]
        group = group.replace(".", "_")
        version = "_".join([group, version_n])
    else:
        version = f'core_{version}'

    try:
        module = importlib.import_module(f'lightkube.resources.{version.lower()}')
    except ImportError as e:
        # It was not a k8s resource and a generic resource was not previously defined
        if client is not None:
            # If we have a client, try to create a generic resource from it
            try:
                model = _create_model_from_client(kind, version_n, client)
            except KeyError as e:
                raise LoadResourceError(
                    f"Unable to implicitly load resource {kind}."
                    f"  Got error: '{e}'"
                )
            return model
        else:
            raise LoadResourceError(f"{e}. If using a CRD, ensure you define a generic resource.")
    return getattr(module, kind)


def _create_model_from_client(kind, version_n, client):
    """Creates a generic resource model from a k8s client.

    TODO: Currently assumes a namespaced resource.  Need to check spec for scope==namespaced, etc
    """
    crd = _get_crd_of_kind(kind, client)
    if crd.spec.scope == "Namespaced":
        creator = create_namespaced_resource
    elif crd.spec.scope == "Cluster":
        creator = create_global_resource
    else:
        raise ValueError(
            f"Unexpected scope for resource of kind {kind}.  Expected 'Namespaced' or 'Cluster',"
            f" got {crd.spec.scope}"
        )

    model = creator(**_crd_to_dict(crd, version_n))
    return model


def _crd_to_dict(crd, version_n):
    return {
        "group": crd.spec.group,
        "version": version_n,
        "kind": crd.spec.names.kind,
        "plural": crd.spec.names.plural,
    }


def _get_crd_of_kind(kind: str, client: Client):
    crds = client.list(CustomResourceDefinition)
    crd = next((c for c in crds if c.spec.names.kind == kind), None)
    if crd:
        return crd
    else:
        raise KeyError(f"Could not find CRD for kind {kind} in Kubernetes cluster")



def from_dict(d: dict, client=None) -> AnyResource:
    """Converts a kubernetes resource defined as python dict to the corresponding resource object.
    If the dict represent a standard resource, the function will automatically load the appropriate
    resource type. Generic resources are also supported and used assuming they were defined prior to
    the function call. Returns the resource object or raise a `LoadResourceError`.

    **parameters**

    * **d** - A dictionary representing a Kubernetes resource. Keys `apiVersion` and `kind` are
      always required.
    * **client** - (Optional) A lightkube.Client used to infer the Resource definition for any 
                   unknown CR
    """
    for attr in REQUIRED_ATTR:
        if attr not in d:
            raise LoadResourceError(f"Invalid resource definition, key '{attr}' missing.")

    model = _load_model(d['apiVersion'], d['kind'], client=client)
    return model.from_dict(d)


def load_all_yaml(stream: Union[str, TextIO], context: dict = None, template_env = None, client=None) -> List[AnyResource]:
    """Load kubernetes resource objects defined as YAML. See `from_dict` regarding how resource types are detected.
    Returns a list of resource objects or raise a `LoadResourceError`.

    **parameters**

    * **stream** - A file-like object or a string representing a yaml file or a template resulting in
        a yaml file.
    * **context** - When is not `None` the stream is considered a `jinja2` template and the `context`
        will be used during templating.
    * **template_env** - `jinja2` template environment to be used for templating. When absent a standard
        environment is used.
    * **client** - (Optional) A lightkube.Client used to infer the Resource definition for any 
                   unknown CR

    **NOTE**: When using the template functionality (setting the context parameter), the dependency
        module `jinja2` need to be installed.
    """
    if context is not None:
        stream = _template(stream, context=context, template_env=template_env)
    res = []
    for obj in yaml.safe_load_all(stream):
         res.append(from_dict(obj, client=client))
    return res


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
