from collections import namedtuple
import pytest

from lightkube import sort_objects


@pytest.fixture()
def resources_in_apply_order():
    mock_resource = namedtuple("resource", ("kind",))
    resources = [
        mock_resource(kind="CustomResourceDefinition"),
        mock_resource(kind="Namespace"),
        mock_resource(kind="Secret"),
        mock_resource(kind="ServiceAccount"),
        mock_resource(kind="PersistentVolume"),
        mock_resource(kind="PersistentVolumeClaim"),
        mock_resource(kind="ConfigMap"),
        mock_resource(kind="Role"),
        mock_resource(kind="ClusterRole"),
        mock_resource(kind="RoleBinding"),
        mock_resource(kind="ClusterRoleBinding"),
        mock_resource(kind="something-else"),
    ]
    return resources


@pytest.mark.parametrize(
    "reverse",
    [
        False,  # Desired result in apply-friendly order
        True,   # Desired order in delete-friendly order
    ]
)
def test_sort_objects_by_kind(reverse, resources_in_apply_order):
    """Tests that sort_objects can kind-sort objects in both apply and delete orders."""
    resources_expected_order = resources_in_apply_order
    if reverse:
        resources_expected_order = list(reversed(resources_expected_order))

    # Add disorder to the test input
    resources_unordered = resources_expected_order[1:] + [resources_expected_order[0]]

    result = sort_objects(resources_unordered, reverse=reverse)
    assert result == resources_expected_order
