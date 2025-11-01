import enum
import typing
from dataclasses import dataclass


class PatchType(enum.Enum):
    """
    Attributes:
      JSON: Execute a json patch
      MERGE: Execute a json merge patch
      STRATEGIC: Execute a strategic merge patch
      APPLY: Execute a [server side apply](https://kubernetes.io/docs/reference/using-api/server-side-apply/)
    """

    JSON = "application/json-patch+json"
    MERGE = "application/merge-patch+json"
    STRATEGIC = "application/strategic-merge-patch+json"
    APPLY = "application/apply-patch+yaml"


class CascadeType(enum.Enum):
    """
    Attributes:
      ORPHAN: orphan the dependents
      BACKGROUND: allow the garbage collector to delete the dependents in the background
      FOREGROUND: a cascading policy that deletes all dependents in the foreground
    """

    ORPHAN = "Orphan"
    BACKGROUND = "Background"
    FOREGROUND = "Foreground"


class OnErrorAction(enum.Enum):
    """
    Attributes:
      RETRY: Retry to perform the API call again from the last version
      STOP: Stop silently the iterator
      RAISE: Raise the error on the caller scope
    """

    RETRY = 0
    STOP = 1
    RAISE = 2


@dataclass
class OnErrorResult:
    action: OnErrorAction
    sleep: float = 0


OnErrorHandler = typing.Callable[[Exception, int], OnErrorResult]


def on_error_raise(e: Exception, count: int):
    """Raise the error on the caller scope"""
    return OnErrorResult(OnErrorAction.RAISE)


def on_error_stop(e: Exception, count: int):
    """Stop silently the iterator"""
    return OnErrorResult(OnErrorAction.STOP)


def on_error_retry(e: Exception, count: int):
    """Retry to perform the API call again from the last version"""
    return OnErrorResult(OnErrorAction.RETRY)
