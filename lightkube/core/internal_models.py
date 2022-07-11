import sys

try:
    from ..models import meta_v1, autoscaling_v1, core_v1

    try:
        from ..models import apiextensions_v1 as apiextensions
    except:
        from ..models import apiextensions_v1beta1 as apiextensions
except:
    if sys.modules["__main__"].__package__ != 'mkdocs':   # we ignore this import error during documentation generation
        raise
    from unittest import mock


    class CustomResourceDefinition:
        pass

    apiextensions = mock.Mock()
    apiextensions.CustomResourceDefinition = CustomResourceDefinition


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
