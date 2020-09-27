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


class ApiError(httpx.HTTPStatusError):
    def __init__(
            self, request: httpx.Request = None, response: httpx.Response = None) -> None:
        self.status = meta_v1.Status.from_dict(response.json())
        super().__init__(self.status.message, request=request, response=response)
