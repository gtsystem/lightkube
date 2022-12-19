import enum
from dataclasses import dataclass
import typing


class PatchType(enum.Enum):
    JSON = 'application/json-patch+json'
    MERGE = 'application/merge-patch+json'
    STRATEGIC = 'application/strategic-merge-patch+json'
    APPLY = 'application/apply-patch+yaml'

class CascadeType(enum.Enum):
    ORPHAN = 'Orphan'
    BACKGROUND = 'Background'
    FOREGROUND = 'Foreground'

class OnErrorAction(enum.Enum):
    RETRY = 0       # retry to perform the API call again from the last version
    STOP = 1        # stop silently the iterator
    RAISE = 2       # raise the error on the caller scope


@dataclass
class OnErrorResult:
    action: OnErrorAction
    sleep: float = 0


OnErrorHandler = typing.Callable[[Exception, int], OnErrorResult]


def on_error_raise(e, count):
    return OnErrorResult(OnErrorAction.RAISE)


def on_error_stop(e, count):
    return OnErrorResult(OnErrorAction.STOP)


def on_error_retry(e, count):
    return OnErrorResult(OnErrorAction.RETRY)
