"""
This module exposes dependencies used by lightkube-models

These dependencies are here because we may decide to replace dataclasses with something else in the future
"""
from dataclasses import dataclass, field

from .dataclasses_dict import DataclassDictMixIn as DictMixin
