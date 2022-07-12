import sys

try:
    from ..resources import core_v1

    try:
        from ..resources import apiextensions_v1 as apiextensions
    except:
        from ..resources import apiextensions_v1beta1 as apiextensions
except:
    if sys.modules["__main__"].__package__ != 'mkdocs':   # we ignore this import error during documentation generation
        raise
    from unittest import mock


    class CustomResourceDefinition:
        pass

    apiextensions = mock.Mock()
    apiextensions.CustomResourceDefinition = CustomResourceDefinition


    class PodLog:
        pass

    core_v1 = mock.Mock()
    core_v1.PodLog = PodLog
