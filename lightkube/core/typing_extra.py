"""This module provides a compatibility layer for functions in typing that appeared on 3.8"""
import collections.abc
import sys

if sys.version_info[:2] > (3, 7):
    from typing import get_args, get_origin

else:
    def get_origin(tp):
        if hasattr(tp, '__origin__'):
            return tp.__origin__
        return None


    def get_args(tp):
        if hasattr(tp, '__args__'):
            res = tp.__args__
            if get_origin(tp) is collections.abc.Callable and res[0] is not Ellipsis:
                res = (list(res[:-1]), res[-1])
            return res
        return ()
