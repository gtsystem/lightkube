from collections import defaultdict
from typing import List
from ..core import resource as r


def sort_objects(objs: List[r.Resource], by: str = "kind", reverse: bool = False) -> List[r.Resource]:
    """Sorts a list of resource objects by a sorting schema, returning a new list

    **parameters**

    * **objs** - list of resource objects to be sorted
    * **by** - *(optional)* sorting schema. Possible values:
        * `'kind'` - sorts by kind, ranking objects in an order that is suitable for batch-applying
          many resources.  For example, Namespaces and ServiceAccounts are sorted ahead of
          ClusterRoleBindings or Pods that might use them.  The reverse of this order is suitable
          for batch-deleting.
          See _kind_rank_function for full details on sorting
    * **reverse** - *(optional)* if `True`, sorts in reverse order
    """
    if by == "kind":
        objs = sorted(objs, key=_kind_rank_function, reverse=reverse)
    else:
        raise ValueError(f"Unknown sorting schema: {by}")
    return objs


UNKNOWN_ITEM_SORT_VALUE = 1000
RANK_ORDER = {
    "CustomResourceDefinition": 10,
    "Namespace": 20,
    "Secret": 31,
    "ServiceAccount": 32,
    "PersistentVolume": 33,
    "PersistentVolumeClaim": 34,
    "ConfigMap": 35,
    "Role": 41,
    "ClusterRole": 42,
    "RoleBinding": 43,
    "ClusterRoleBinding": 44,
}


def _kind_rank_function(obj: List[r.Resource]) -> int:
    """
    Returns an integer rank based on an objects .kind

    Ranking is set to order kinds by:
    * CRDs
    * Namespaces
    * Things that might be referenced by pods (Secret, ServiceAccount, PVs/PVCs, ConfigMap)
    * RBAC
        * Roles and ClusterRoles
        * RoleBindings and ClusterRoleBindings
    * Everything else (Pod, Deployment, ...)
    """
    return RANK_ORDER.get(obj.kind, UNKNOWN_ITEM_SORT_VALUE)
