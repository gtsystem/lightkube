import sys

try:
    from ..models import meta_v1, autoscaling_v1, core_v1

except:
    if sys.modules["__main__"].__package__ != 'mkdocs':   # we ignore this import error during documentation generation
        raise
    from unittest import mock


    class ObjectMeta:
        pass

    meta_v1 = mock.Mock()
    meta_v1.ObjectMeta = ObjectMeta


    class Scale:
        pass

    autoscaling_v1 = mock.Mock()
    autoscaling_v1.Scale = Scale


    class ResourceRequirements:
        pass

    core_v1 = mock.Mock()
    core_v1.ResourceRequirements = ResourceRequirements
