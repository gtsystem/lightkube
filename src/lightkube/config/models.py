import base64
import tempfile
from dataclasses import dataclass, field
from typing import IO, Dict, List, Optional, overload

from ..core.dataclasses_dict import DataclassDictMixIn


class FileStr(str):
    handler: Optional[IO[bytes]] = None

    # TODO: Remove non-typechecking compliant tricks here (a `__new__` function that doesn't return the class itself,
    #   but either `str` (which at least is a subclass) or `None`) and use factory methods instead of overwriting
    #   `__new__` or just have a custom class with a `__init__` method.
    @overload
    def __new__(cls, data: None) -> None: ...  # type: ignore[misc]
    @overload
    def __new__(cls, data: str) -> str: ...  # type: ignore[misc]

    def __new__(cls, data: Optional[str]) -> Optional[str]:  # type: ignore[misc]
        if data is None:
            return None

        f = tempfile.NamedTemporaryFile()
        f.write(base64.b64decode(data))
        f.flush()
        file = str.__new__(cls, f.name)
        file.handler = f
        return file

    def __del__(self) -> None:
        if self.handler:
            self.handler.close()
            self.handler = None


@dataclass
class Context(DataclassDictMixIn):
    cluster: str
    user: Optional[str] = None
    namespace: Optional[str] = None


@dataclass
class NameValue(DataclassDictMixIn):
    name: str
    value: str


@dataclass
class UserExec(DataclassDictMixIn):
    apiVersion: str
    command: str
    env: List[NameValue] = field(default_factory=list)
    args: List[str] = field(default_factory=list)
    installHint: Optional[str] = None


@dataclass
class User(DataclassDictMixIn):
    exec: Optional[UserExec] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    auth_provider: Optional[Dict] = field(metadata={"json": "auth-provider"}, default=None)
    client_cert: Optional[str] = field(metadata={"json": "client-certificate"}, default=None)
    client_cert_data: Optional[str] = field(metadata={"json": "client-certificate-data"}, default=None)
    client_key: Optional[str] = field(metadata={"json": "client-key"}, default=None)
    client_key_data: Optional[str] = field(metadata={"json": "client-key-data"}, default=None)


@dataclass
class Cluster(DataclassDictMixIn):
    """
    Attributes:
      server: the server name
    """

    server: str = "http://localhost:8080"
    certificate_auth: Optional[str] = field(metadata={"json": "certificate-authority"}, default=None)
    certificate_auth_data: Optional[str] = field(metadata={"json": "certificate-authority-data"}, default=None)
    insecure: bool = field(metadata={"json": "insecure-skip-tls-verify"}, default=False)
