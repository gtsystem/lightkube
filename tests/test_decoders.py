"""Tests for lightkube.core.decoders."""

import json
from typing import Optional

import msgspec
import pytest

from lightkube.core.decoders import (
    decode_list,
    decode_object,
    decode_status,
    decode_watch_event,
)
from lightkube.generic_resource import create_global_resource, create_namespaced_resource

# ---------------------------------------------------------------------------
# Local resource definitions (normal msgspec.Struct-based resource)
# ---------------------------------------------------------------------------


class PodSpec(msgspec.Struct, omit_defaults=True):
    nodeName: Optional[str] = None
    restartPolicy: Optional[str] = None


class PodStatus(msgspec.Struct, omit_defaults=True):
    phase: Optional[str] = None


class Pod(msgspec.Struct, omit_defaults=True):
    """Minimal Pod-like normal resource backed by msgspec.Struct."""

    apiVersion: Optional[str] = None
    kind: Optional[str] = None
    spec: Optional[PodSpec] = None
    status: Optional[PodStatus] = None


# ---------------------------------------------------------------------------
# Generic resource definitions via the real lightkube helpers
# ---------------------------------------------------------------------------

# Namespaced generic resource (e.g. a CRD scoped to a namespace)
Widget = create_namespaced_resource("example.io", "v1", "Widget", "widgets")

# Cluster-scoped generic resource
Cluster = create_global_resource("example.io", "v1", "Cluster", "clusters")


# ---------------------------------------------------------------------------
# decode_watch_event
# ---------------------------------------------------------------------------


class TestDecodeWatchEvent:
    def _make_event(self, event_type: str, obj: dict) -> bytes:
        return json.dumps({"type": event_type, "object": obj}).encode()

    def test_added_event(self):
        line = self._make_event("ADDED", {"apiVersion": "v1", "kind": "Pod"})
        event = decode_watch_event(line)
        assert event.type == "ADDED"
        # object is returned as msgspec.Raw — verify it is decodable back to the dict
        decoded_obj = msgspec.json.decode(event.object)
        assert decoded_obj["kind"] == "Pod"

    def test_modified_event(self):
        line = self._make_event("MODIFIED", {"status": {"phase": "Running"}})
        event = decode_watch_event(line)
        assert event.type == "MODIFIED"

    def test_deleted_event(self):
        line = self._make_event("DELETED", {"metadata": {"name": "mypod"}})
        event = decode_watch_event(line)
        assert event.type == "DELETED"

    def test_object_is_raw(self):
        line = self._make_event("ADDED", {"foo": "bar"})
        event = decode_watch_event(line)
        # WatchEvent.object must be msgspec.Raw, not a decoded dict
        assert isinstance(event.object, msgspec.Raw)

    def test_invalid_json_raises(self):
        with pytest.raises(msgspec.DecodeError):
            decode_watch_event(b"not-json")


# ---------------------------------------------------------------------------
# decode_status
# ---------------------------------------------------------------------------


class TestDecodeStatus:
    def _make_status(self, **kwargs) -> bytes:
        payload = {"apiVersion": "v1", "kind": "Status", **kwargs}
        return json.dumps(payload).encode()

    def test_success_status(self):
        data = self._make_status(status="Success", code=200, message="OK")
        status = decode_status(data)
        assert status.status == "Success"
        assert status.code == 200
        assert status.message == "OK"

    def test_failure_status(self):
        data = self._make_status(status="Failure", code=404, reason="NotFound", message="pod not found")
        status = decode_status(data)
        assert status.status == "Failure"
        assert status.code == 404
        assert status.reason == "NotFound"

    def test_minimal_status(self):
        data = json.dumps({"apiVersion": "v1", "kind": "Status"}).encode()
        status = decode_status(data)
        # All optional fields default to None
        assert status.code is None
        assert status.message is None

    def test_invalid_json_raises(self):
        with pytest.raises(msgspec.DecodeError):
            decode_status(b"{{bad")


# ---------------------------------------------------------------------------
# decode_object  — normal (Struct) resource
# ---------------------------------------------------------------------------


class TestDecodeObjectStruct:
    def _pod_bytes(self, **kwargs) -> bytes:
        return json.dumps({"apiVersion": "v1", "kind": "Pod", **kwargs}).encode()

    def test_basic_decode(self):
        data = self._pod_bytes(spec={"nodeName": "node-1"})
        pod = decode_object(data, Pod)
        assert isinstance(pod, Pod)
        assert pod.apiVersion == "v1"
        assert pod.spec.nodeName == "node-1"

    def test_nested_struct(self):
        data = self._pod_bytes(
            spec={"nodeName": "node-2", "restartPolicy": "Always"},
            status={"phase": "Running"},
        )
        pod = decode_object(data, Pod)
        assert pod.spec.restartPolicy == "Always"
        assert pod.status.phase == "Running"

    def test_returns_correct_type(self):
        data = self._pod_bytes()
        pod = decode_object(data, Pod)
        assert type(pod) is Pod

    def test_missing_optional_fields_default_to_none(self):
        data = json.dumps({}).encode()
        pod = decode_object(data, Pod)
        assert pod.spec is None
        assert pod.status is None

    def test_invalid_json_raises(self):
        with pytest.raises(msgspec.DecodeError):
            decode_object(b"!!!", Pod)


# ---------------------------------------------------------------------------
# decode_object  — generic resource
# ---------------------------------------------------------------------------


class TestDecodeObjectGeneric:
    def test_namespaced_generic_basic(self):
        data = json.dumps({"apiVersion": "example.io/v1", "kind": "Widget", "spec": {"color": "blue"}}).encode()
        obj = decode_object(data, Widget)
        assert isinstance(obj, Widget)
        assert obj["apiVersion"] == "example.io/v1"
        assert obj["spec"]["color"] == "blue"

    def test_namespaced_generic_arbitrary_keys(self):
        payload = {"metadata": {"name": "my-widget", "namespace": "default"}, "data": {"key": "value"}}
        data = json.dumps(payload).encode()
        obj = decode_object(data, Widget)
        assert obj["metadata"]["name"] == "my-widget"
        assert obj["data"]["key"] == "value"

    def test_global_generic_basic(self):
        data = json.dumps({"apiVersion": "example.io/v1", "kind": "Cluster", "spec": {"region": "us-east-1"}}).encode()
        obj = decode_object(data, Cluster)
        assert isinstance(obj, Cluster)
        assert obj["spec"]["region"] == "us-east-1"

    def test_global_generic_returns_correct_type(self):
        data = json.dumps({"apiVersion": "example.io/v1", "kind": "Cluster"}).encode()
        obj = decode_object(data, Cluster)
        assert type(obj) is Cluster


# ---------------------------------------------------------------------------
# decode_list  — normal (Struct) resource
# ---------------------------------------------------------------------------


class TestDecodeListStruct:
    def _make_list(self, items, metadata=None) -> bytes:
        payload: dict = {"items": items}
        if metadata is not None:
            payload["metadata"] = metadata
        return json.dumps(payload).encode()

    def test_empty_list(self):
        data = self._make_list([])
        cont, _rv, items = decode_list(data, Pod)
        assert items == []
        assert cont is None

    def test_single_item(self):
        data = self._make_list([{"apiVersion": "v1", "kind": "Pod", "spec": {"nodeName": "n1"}}])
        _cont, _rv, items = decode_list(data, Pod)
        assert len(items) == 1
        assert isinstance(items[0], Pod)
        assert items[0].spec.nodeName == "n1"

    def test_multiple_items(self):
        pods = [{"apiVersion": "v1", "kind": "Pod", "spec": {"nodeName": f"n{i}"}} for i in range(3)]
        data = self._make_list(pods)
        _cont, _rv, items = decode_list(data, Pod)
        assert len(items) == 3
        assert all(isinstance(p, Pod) for p in items)
        node_names = [p.spec.nodeName for p in items]
        assert node_names == ["n0", "n1", "n2"]

    def test_continue_token(self):
        data = self._make_list([], metadata={"continue": "next-page-token", "resourceVersion": "42"})
        cont, rv, _items = decode_list(data, Pod)
        assert cont == "next-page-token"
        assert rv == "42"

    def test_no_continue_when_last_page(self):
        data = self._make_list([], metadata={"resourceVersion": "100"})
        cont, rv, _items = decode_list(data, Pod)
        assert cont is None
        assert rv == "100"

    def test_no_metadata(self):
        data = self._make_list([])
        cont, rv, _items = decode_list(data, Pod)
        assert cont is None
        assert rv is None

    def test_list_model_is_cached(self):
        """Calling decode_list twice for the same type reuses the cached model."""
        from lightkube.core.decoders import _list_models

        data = self._make_list([])
        decode_list(data, Pod)
        assert Pod in _list_models

        cached_before = _list_models[Pod]
        decode_list(data, Pod)
        assert _list_models[Pod] is cached_before


# ---------------------------------------------------------------------------
# decode_list  — generic resource
# ---------------------------------------------------------------------------


class TestDecodeListGeneric:
    def _make_list(self, items, metadata=None) -> bytes:
        payload: dict = {"items": items}
        if metadata is not None:
            payload["metadata"] = metadata
        return json.dumps(payload).encode()

    def test_namespaced_empty_list(self):
        data = self._make_list([])
        cont, _rv, items = decode_list(data, Widget)
        assert items == []
        assert cont is None

    def test_namespaced_items_are_wrapped(self):
        raw_items = [
            {"apiVersion": "example.io/v1", "kind": "Widget", "metadata": {"name": "w1"}},
            {"apiVersion": "example.io/v1", "kind": "Widget", "metadata": {"name": "w2"}},
        ]
        data = self._make_list(raw_items)
        _cont, _rv, items = decode_list(data, Widget)
        assert len(items) == 2
        assert all(isinstance(i, Widget) for i in items)
        assert items[0]["metadata"]["name"] == "w1"
        assert items[1]["metadata"]["name"] == "w2"

    def test_namespaced_continue_and_resource_version(self):
        data = self._make_list([], metadata={"continue": "tok", "resourceVersion": "7"})
        cont, rv, _items = decode_list(data, Widget)
        assert cont == "tok"
        assert rv == "7"

    def test_global_empty_list(self):
        data = self._make_list([])
        _cont, _rv, items = decode_list(data, Cluster)
        assert items == []

    def test_global_items_are_wrapped(self):
        raw_items = [
            {"apiVersion": "example.io/v1", "kind": "Cluster", "metadata": {"name": "prod"}},
            {"apiVersion": "example.io/v1", "kind": "Cluster", "metadata": {"name": "staging"}},
        ]
        data = self._make_list(raw_items)
        _cont, _rv, items = decode_list(data, Cluster)
        assert len(items) == 2
        assert all(isinstance(i, Cluster) for i in items)
        assert items[0]["metadata"]["name"] == "prod"
        assert items[1]["metadata"]["name"] == "staging"

    def test_global_continue_and_resource_version(self):
        data = self._make_list([], metadata={"continue": "page2", "resourceVersion": "99"})
        cont, rv, _items = decode_list(data, Cluster)
        assert cont == "page2"
        assert rv == "99"
