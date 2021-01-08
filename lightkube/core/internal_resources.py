import sys

try:
    from ..resources import core_v1
except:
    if sys.modules["__main__"].__package__ != 'mkdocs':   # we ignore this import error during documentation generation
        raise
    from unittest import mock

    class PodLog:
        pass

    core_v1 = mock.Mock()
    core_v1.PodLog = PodLog
