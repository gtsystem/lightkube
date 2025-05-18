from typing import (
    Type,
    Iterator,
    TypeVar,
    Union,
    overload,
    Dict,
    Tuple,
    List,
    Iterable,
)
import httpx
from ..config.kubeconfig import SingleConfig, KubeConfig
from .. import operators
from ..core import resource as r
from .generic_client import GenericSyncClient, ListIterable
from ..core.exceptions import ConditionError, ObjectDeleted
from ..types import OnErrorHandler, PatchType, CascadeType, on_error_raise
from .internal_resources import core_v1
from .selector import build_selector

NamespacedResource = TypeVar("NamespacedResource", bound=r.NamespacedResource)
GlobalResource = TypeVar("GlobalResource", bound=r.GlobalResource)
GlobalSubResource = TypeVar("GlobalSubResource", bound=r.GlobalSubResource)
NamespacedSubResource = TypeVar("NamespacedSubResource", bound=r.NamespacedSubResource)
AllNamespacedResource = TypeVar(
    "AllNamespacedResource", bound=Union[r.NamespacedResource, r.NamespacedSubResource]
)
Resource = TypeVar("Resource", bound=r.Resource)
LabelValue = Union[str, None, operators.Operator, Iterable]
FieldValue = Union[str, operators.BinaryOperator, operators.SequenceOperator]
LabelSelector = Dict[str, LabelValue]
FieldSelector = Dict[str, FieldValue]


class Client:
    """Create a new lightkube client

    Parameters:
      config: Instance of `SingleConfig` or `KubeConfig`. When not set the configuration will be detected automatically
        using the following order: in-cluster config, `KUBECONFIG` environment variable, `~/.kube/config` file.
      namespace: Default namespace to use. This attribute is used in case namespaced resources are called without
        defining a namespace. If not specified, the default namespace set in your kube configuration will be used.
      timeout: Instance of `httpx.Timeout`. By default, all timeouts are set to 10 seconds. Notice that read timeout
        is ignored when watching changes.
      lazy: When set, the returned objects will be decoded from the JSON payload in a lazy way, i.e. only when
        accessed.
      field_manager: Name associated with the actor or entity that is making these changes.
      trust_env: Ignore environment variables, also passed through to httpx.Client trust_env.  See its
        docs for further description. If False, empty config will be derived from_file(DEFAULT_KUBECONFIG)
      dry_run: Apply server-side dry-run and guarantee that modifications will not
        be persisted in storage. Setting this field to `True` is equivalent of passing `--dry-run=server`
        to `kubectl` commands.
      transport: Custom httpx transport.
      proxy: HTTP proxy for the httpx client.
    """

    def __init__(
        self,
        config: Union[SingleConfig, KubeConfig, None] = None,
        namespace: str = None,
        timeout: httpx.Timeout = None,
        lazy=True,
        field_manager: str = None,
        trust_env: bool = True,
        dry_run: bool = False,
        transport: httpx.BaseTransport = None,
        proxy: str = None,
    ):
        self._client = GenericSyncClient(
            config,
            namespace=namespace,
            timeout=timeout,
            lazy=lazy,
            field_manager=field_manager,
            trust_env=trust_env,
            dry_run=dry_run,
            transport=transport,
            proxy=proxy,
        )

    @property
    def namespace(self):
        """Return the default namespace that will be used when a namespace has not been specified"""
        return self._client.namespace

    @property
    def config(self) -> SingleConfig:
        """Return the kubernetes configuration used in this client"""
        return self._client.config

    @overload
    def delete(
        self,
        res: Type[GlobalResource],
        name: str,
        grace_period: int = None,
        cascade: CascadeType = None,
        dry_run: bool = False,
    ) -> None: ...

    @overload
    def delete(
        self,
        res: Type[NamespacedResource],
        name: str,
        *,
        namespace: str = None,
        grace_period: int = None,
        cascade: CascadeType = None,
        dry_run: bool = False,
    ) -> None: ...

    def delete(
        self,
        res,
        name: str,
        *,
        namespace: str = None,
        grace_period: int = None,
        cascade: CascadeType = None,
        dry_run: bool = False,
    ):
        """Delete an object. Raise [lightkube.ApiError][] if the object doesn't exist.

        Parameters:
            res: Resource kind.
            name: Name of the object to delete.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
            grace_period: The duration in seconds before the object should be deleted.
                Value must be non-negative integer. The value zero indicates delete immediately. If this value is `None`
                (default), the default grace period for the specified type will be used. Defaults to a per object value if
                not specified. Zero means delete immediately.
            cascade: Whether and how garbage collection will be performed. Either this field or
                OrphanDependents may be set, but not both. The default policy is decided by the existing finalizer set
                in the metadata.finalizers and the resource-specific default policy. Acceptable values are:

                * `CascadeType.ORPHAN` - orphan the dependents;
                * `CascadeType.BACKGROUND` - allow the garbage collector to delete the dependents in the background;
                * `CascadeType.FOREGROUND` - a cascading policy that deletes all dependents in the foreground.
            dry_run: Apply server-side dry-run and guarantee that modifications will not
                be persisted in storage. Setting this field to `True` is equivalent of passing `--dry-run=server`
                to `kubectl` commands.
        """
        return self._client.request(
            "delete",
            res=res,
            name=name,
            namespace=namespace,
            params={
                "gracePeriodSeconds": grace_period,
                "propagationPolicy": cascade.value if cascade else None,
                "dryRun": "All" if dry_run else None,
            },
        )

    @overload
    def deletecollection(
        self,
        res: Type[GlobalResource],
        grace_period: int = None,
        cascade: CascadeType = None,
        dry_run: bool = False,
    ) -> None: ...

    @overload
    def deletecollection(
        self,
        res: Type[NamespacedResource],
        *,
        namespace: str = None,
        grace_period: int = None,
        cascade: CascadeType = None,
        dry_run: bool = False,
    ) -> None: ...

    def deletecollection(
        self,
        res,
        *,
        namespace: str = None,
        grace_period: int = None,
        cascade: CascadeType = None,
        dry_run: bool = False,
    ):
        """Delete all objects of the given kind

        Parameters:
            res: Resource kind.
            namespace: *(optional)* Name of the namespace containing the object (Only for namespaced resources).
            grace_period: The duration in seconds before the objects should be deleted.
                Value must be non-negative integer. The value zero indicates delete immediately. If this value is `None`
                (default), the default grace period for the specified type will be used. Defaults to a per object value if
                not specified. Zero means delete immediately.
            cascade: Whether and how garbage collection will be performed. Either this field or
                OrphanDependents may be set, but not both. The default policy is decided by the existing finalizer set
                in the metadata.finalizers and the resource-specific default policy. Acceptable values are:

                * 'CascadeType.ORPHAN' - orphan the dependents;
                * 'CascadeType.BACKGROUND' - allow the garbage collector to delete the dependents in the background;
                * 'CascadeType.FOREGROUND' - a cascading policy that deletes all dependents in the foreground.
            dry_run: Apply server-side dry-run and guarantee that modifications will not
                be persisted in storage. Setting this field to `True` is equivalent of passing `--dry-run=server`
                to `kubectl` commands.
        """
        return self._client.request(
            "deletecollection",
            res=res,
            namespace=namespace,
            params={
                "gracePeriodSeconds": grace_period,
                "propagationPolicy": cascade.value if cascade else None,
                "dryRun": "All" if dry_run else None,
            },
        )

    @overload
    def get(self, res: Type[GlobalResource], name: str) -> GlobalResource: ...

    @overload
    def get(
        self, res: Type[AllNamespacedResource], name: str, *, namespace: str = None
    ) -> AllNamespacedResource: ...

    def get(self, res, name, *, namespace=None):
        """Return an object. Raise `lightkube.ApiError` if the object doesn't exist.

        Parameters:
            res: Resource kind.
            name: Name of the object to fetch.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
        """
        return self._client.request("get", res=res, name=name, namespace=namespace)

    @overload
    def list(
        self,
        res: Type[GlobalResource],
        *,
        chunk_size: int = None,
        labels: LabelSelector = None,
        fields: FieldSelector = None,
    ) -> ListIterable[GlobalResource]: ...

    @overload
    def list(
        self,
        res: Type[NamespacedResource],
        *,
        namespace: str = None,
        chunk_size: int = None,
        labels: LabelSelector = None,
        fields: FieldSelector = None,
    ) -> ListIterable[NamespacedResource]: ...

    def list(self, res, *, namespace=None, chunk_size=None, labels=None, fields=None):
        """Return an iterator of objects matching the selection criteria.

        Parameters:
            res: resource kind.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
            chunk_size: Limit the amount of objects returned for each rest API call.
                 This method will automatically execute all subsequent calls until no more data is available.
            labels: Limit the returned objects by labels. More [details](../selectors.md).
            fields: Limit the returned objects by fields. More [details](../selectors.md).
        """

        br = self._client.prepare_request(
            "list",
            res=res,
            namespace=namespace,
            params={
                "limit": chunk_size,
                "labelSelector": build_selector(labels) if labels else None,
                "fieldSelector": (
                    build_selector(fields, for_fields=True) if fields else None
                ),
            },
        )
        return self._client.list(br)

    @overload
    def watch(
        self,
        res: Type[GlobalResource],
        *,
        labels: LabelSelector = None,
        fields: FieldSelector = None,
        server_timeout: int = None,
        resource_version: str = None,
        on_error: OnErrorHandler = on_error_raise,
    ) -> Iterator[Tuple[str, GlobalResource]]: ...

    @overload
    def watch(
        self,
        res: Type[NamespacedResource],
        *,
        namespace: str = None,
        labels: LabelSelector = None,
        fields: FieldSelector = None,
        server_timeout: int = None,
        resource_version: str = None,
        on_error: OnErrorHandler = on_error_raise,
    ) -> Iterator[Tuple[str, NamespacedResource]]: ...

    def watch(
        self,
        res,
        *,
        namespace=None,
        labels=None,
        fields=None,
        server_timeout=None,
        resource_version=None,
        on_error=on_error_raise,
    ):
        """Watch changes to objects

        Parameters:
            res: resource kind.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
            labels: Limit the returned objects by labels. More [details](../selectors.md).
            fields: Limit the returned objects by fields. More [details](../selectors.md).
            server_timeout: Server side timeout in seconds to close a watch request.
                This method will automatically create a new request whenever the backend close the connection
                without errors.
            resource_version: When set, only modification events following this version will be returned.
            on_error: Function that control what to do in case of errors.
                The default implementation will raise any error.
        """
        br = self._client.prepare_request(
            "list",
            res=res,
            namespace=namespace,
            watch=True,
            params={
                "timeoutSeconds": server_timeout,
                "resourceVersion": resource_version,
                "labelSelector": build_selector(labels) if labels else None,
                "fieldSelector": (
                    build_selector(fields, for_fields=True) if fields else None
                ),
            },
        )
        return self._client.watch(br, on_error=on_error)

    @overload
    def wait(
        self,
        res: Type[GlobalResource],
        name: str,
        *,
        for_conditions: Iterable[str],
        raise_for_conditions: Iterable[str] = (),
    ) -> GlobalResource: ...

    @overload
    def wait(
        self,
        res: Type[AllNamespacedResource],
        name: str,
        *,
        for_conditions: Iterable[str],
        namespace: str = None,
        raise_for_conditions: Iterable[str] = (),
    ) -> AllNamespacedResource: ...

    def wait(
        self,
        res,
        name: str,
        *,
        for_conditions: Iterable[str],
        namespace=None,
        raise_for_conditions: Iterable[str] = (),
    ):
        """Wait for the specified conditions.
        Raise `lightkube.ObjectDeleted` if the object get deleted during waiting.

        Parameters:
            res: Resource kind.
            name: Name of resource to wait for.
            for_conditions: Condition types that are considered a success and will end the wait.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
            raise_for_conditions: Condition types that are considered failures and will exit the wait early
                with `lightkube.ConditionError`.
        """

        kind = r.api_info(res).plural
        full_name = f"{kind}/{name}"

        for_conditions = list(for_conditions)
        raise_for_conditions = list(raise_for_conditions)

        for op, obj in self.watch(
            res, namespace=namespace, fields={"metadata.name": name}
        ):
            if obj.status is None:
                continue

            if op == "DELETED":
                raise ObjectDeleted(full_name)

            try:
                status = obj.status.to_dict()
            except AttributeError:
                status = obj.status

            conditions = [
                c for c in status.get("conditions", []) if c["status"] == "True"
            ]
            if any(c["type"] in for_conditions for c in conditions):
                return obj

            failures = [c for c in conditions if c["type"] in raise_for_conditions]

            if failures:
                raise ConditionError(
                    full_name, [f.get("message", f["type"]) for f in failures]
                )

    @overload
    def patch(
        self,
        res: Type[GlobalSubResource],
        name: str,
        obj: Union[GlobalSubResource, Dict, List],
        *,
        patch_type: PatchType = PatchType.STRATEGIC,
        field_manager: str = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> GlobalSubResource: ...

    @overload
    def patch(
        self,
        res: Type[GlobalResource],
        name: str,
        obj: Union[GlobalResource, Dict, List],
        *,
        patch_type: PatchType = PatchType.STRATEGIC,
        field_manager: str = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> GlobalResource: ...

    @overload
    def patch(
        self,
        res: Type[AllNamespacedResource],
        name: str,
        obj: Union[AllNamespacedResource, Dict, List],
        *,
        namespace: str = None,
        patch_type: PatchType = PatchType.STRATEGIC,
        field_manager: str = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> AllNamespacedResource: ...

    def patch(
        self,
        res,
        name,
        obj,
        *,
        namespace=None,
        patch_type=PatchType.STRATEGIC,
        field_manager=None,
        force=False,
        dry_run=False,
    ):
        """Patch an object. Raise lightkube.ApiError if the object doesn't exist.

        Parameters:
            res: Resource kind.
            name: Name of the object to patch.
            obj: patch object.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
            patch_type: Type of patch to execute. Default `PatchType.STRATEGIC`.
            field_manager: Name associated with the actor or entity that is making these changes.
                This parameter overrides the corresponding `Client` initialization parameter.
                **NOTE**: This parameter is mandatory (here or at `Client` creation time) for `PatchType.APPLY`.
            force: Force is going to "force" Apply requests. It means user will re-acquire conflicting
                fields owned by other people. This parameter is ignored for non-apply patch types
            dry_run: Apply server-side dry-run and guarantee that modifications will not
                be persisted in storage. Setting this field to `True` is equivalent of passing `--dry-run=server`
                to `kubectl` commands.
        """
        force_param = "true" if force and patch_type == PatchType.APPLY else None
        return self._client.request(
            "patch",
            res=res,
            name=name,
            namespace=namespace,
            obj=obj,
            headers={"Content-Type": patch_type.value},
            params={
                "force": force_param,
                "fieldManager": field_manager,
                "dryRun": "All" if dry_run else None,
            },
        )

    @overload
    def create(
        self,
        obj: GlobalSubResource,
        name: str,
        field_manager: str = None,
        dry_run: bool = False,
    ) -> GlobalSubResource: ...

    @overload
    def create(
        self,
        obj: NamespacedSubResource,
        name: str,
        *,
        namespace: str = None,
        field_manager: str = None,
        dry_run: bool = False,
    ) -> NamespacedSubResource: ...

    @overload
    def create(
        self, obj: GlobalResource, field_manager: str = None, dry_run: bool = False
    ) -> GlobalResource: ...

    @overload
    def create(
        self, obj: NamespacedResource, field_manager: str = None, dry_run: bool = False
    ) -> NamespacedResource: ...

    def create(
        self, obj, name=None, *, namespace=None, field_manager=None, dry_run=False
    ):
        """Create a new object and return its representation.
        Raise lightkube.ApiError if the object already exist.

        Parameters:
            obj: object to create. This need to be an instance of a resource kind.
            name: Required only for sub-resources: Name of the resource to which this object belongs.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
                If the namespace doesn't exist, `lightkube.ApiError` is raised.
            field_manager: Name associated with the actor or entity that is making these changes.
                This parameter overrides the corresponding `Client` initialization parameter.
            dry_run: Apply server-side dry-run and guarantee that modifications will not
                be persisted in storage. Setting this field to `True` is equivalent of passing `--dry-run=server`
                to `kubectl` commands.
        """
        return self._client.request(
            "post",
            name=name,
            namespace=namespace,
            obj=obj,
            params={
                "fieldManager": field_manager,
                "dryRun": "All" if dry_run else None,
            },
        )

    @overload
    def replace(
        self,
        obj: GlobalSubResource,
        name: str,
        field_manager: str = None,
        dry_run: bool = False,
    ) -> GlobalSubResource: ...

    @overload
    def replace(
        self,
        obj: NamespacedSubResource,
        name: str,
        *,
        namespace: str = None,
        field_manager: str = None,
        dry_run: bool = False,
    ) -> NamespacedSubResource: ...

    @overload
    def replace(
        self, obj: GlobalResource, field_manager: str = None, dry_run: bool = False
    ) -> GlobalResource: ...

    @overload
    def replace(
        self, obj: NamespacedResource, field_manager: str = None, dry_run: bool = False
    ) -> NamespacedResource: ...

    def replace(
        self,
        obj,
        name=None,
        *,
        namespace=None,
        field_manager=None,
        dry_run: bool = False,
    ):
        """Replace an existing resource. Raise `lightkube.ApiError` if the object doesn't exist.

        Parameters:
            obj: new object. This need to be an instance of a resource kind.
            name: Required only for sub-resources: Name of the resource to which this object belongs.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
            field_manager: Name associated with the actor or entity that is making these changes.
                This parameter overrides the corresponding `Client` initialization parameter.
            dry_run: Apply server-side dry-run and guarantee that modifications will not
                be persisted in storage. Setting this field to `True` is equivalent of passing `--dry-run=server`
                to `kubectl` commands.
        """
        return self._client.request(
            "put",
            name=name,
            namespace=namespace,
            obj=obj,
            params={
                "fieldManager": field_manager,
                "dryRun": "All" if dry_run else None,
            },
        )

    @overload
    def log(
        self,
        name: str,
        *,
        namespace: str = None,
        container: str = None,
        follow: bool = False,
        since: int = None,
        tail_lines: int = None,
        timestamps: bool = False,
        newlines: bool = True,
    ) -> Iterator[str]: ...

    def log(
        self,
        name,
        *,
        namespace=None,
        container=None,
        follow=False,
        since=None,
        tail_lines=None,
        timestamps=False,
        newlines=True,
    ):
        """Return log lines for the given Pod. Raise `lightkube.ApiError` if the Pod doesn't exist.

        Parameters:
            name: Name of the Pod.
            namespace: Name of the namespace containing the Pod.
            container: The container for which to stream logs. Defaults to only container if there is one container in the pod.
            follow: If `True`, follow the log stream of the pod.
            since: If set, a relative time in seconds before the current time from which to fetch logs.
            tail_lines: If set, the number of lines from the end of the logs to fetch.
            timestamps: If `True`, add an RFC3339 or RFC3339Nano timestamp at the beginning of every line of log output.
            newlines: If `True`, each line will end with a newline, otherwise the newlines will be stripped.
        """
        br = self._client.prepare_request(
            "get",
            core_v1.PodLog,
            name=name,
            namespace=namespace,
            params={
                "timestamps": timestamps,
                "tailLines": tail_lines,
                "container": container,
                "sinceSeconds": since,
                "follow": follow,
            },
        )
        req = self._client.build_adapter_request(br)
        resp = self._client.send(req, stream=follow)
        self._client.raise_for_status(resp)
        return (l + "\n" if newlines else l for l in resp.iter_lines())

    @overload
    def apply(
        self,
        obj: GlobalSubResource,
        name: str,
        *,
        field_manager: str = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> GlobalSubResource: ...

    @overload
    def apply(
        self,
        obj: NamespacedSubResource,
        name: str,
        *,
        namespace: str = None,
        field_manager: str = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> NamespacedSubResource: ...

    @overload
    def apply(
        self,
        obj: GlobalResource,
        field_manager: str = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> GlobalResource: ...

    @overload
    def apply(
        self,
        obj: NamespacedResource,
        field_manager: str = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> NamespacedResource: ...

    def apply(
        self,
        obj,
        name=None,
        *,
        namespace=None,
        field_manager=None,
        force=False,
        dry_run=False,
    ):
        """Create or configure an object. This method uses the
        [server-side apply](https://kubernetes.io/docs/reference/using-api/server-side-apply/) functionality.

        Parameters:
            obj: object to create. This need to be an instance of a resource kind.
            name: Required only for sub-resources: Name of the resource to which this object belongs.
            namespace: Name of the namespace containing the object (Only for namespaced resources).
                If the namespace doesn't exist, `lightkube.ApiError` is raised.
            field_manager: Name associated with the actor or entity that is making these changes.
            force: Force is going to "force" Apply requests. It means user will re-acquire conflicting
                fields owned by other people.
            dry_run: Apply server-side dry-run and guarantee that modifications will not
                be persisted in storage. Setting this field to `True` is equivalent of passing `--dry-run=server`
                to `kubectl` commands.
        """
        if (
            namespace is None
            and isinstance(obj, r.NamespacedResource)
            and obj.metadata.namespace
        ):
            namespace = obj.metadata.namespace
        if name is None and obj.metadata.name:
            name = obj.metadata.name
        return self.patch(
            type(obj),
            name,
            obj,
            namespace=namespace,
            patch_type=PatchType.APPLY,
            field_manager=field_manager,
            force=force,
            dry_run=dry_run,
        )
