"""
Exceptions.
"""

import httpx

from .internal_models import meta_v1


class ConfigError(Exception):
    """
    Configuration specific errors.
    """

    pass


class NotReadyError(Exception):
    """
    Some information is not ready yet.
    """

    def __init__(self, name: str, message: str) -> None:
        super().__init__()
        self.name = name
        self.message = message

    def __str__(self) -> str:
        return f"{self.name} is not ready yet: {self.message}"


class ApiError(httpx.HTTPStatusError):
    status: "meta_v1.Status"

    def __init__(
        self, request: httpx.Request = None, response: httpx.Response = None
    ) -> None:
        self.status = meta_v1.Status.from_dict(response.json())
        super().__init__(self.status.message, request=request, response=response)


class LoadResourceError(Exception):
    """
    Error in loading a resource
    """


class ObjectDeleted(Exception):
    """
    Object was unexpectedly deleted
    """

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f"{self.name} was unexpectedly deleted"


class ConditionError(Exception):
    """
    Object is in specified bad condition
    """

    def __init__(self, name, messages):
        self.name = name
        self.messages = messages

    def __str__(self):
        messages = "; ".join(self.messages)
        return f"{self.name} has failure condition(s): {messages}"
