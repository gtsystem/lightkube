import base64
import tempfile
from typing import IO, Dict, List, Optional, overload

import msgspec


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


class Context(msgspec.Struct, omit_defaults=True):
    cluster: str
    user: Optional[str] = None
    namespace: Optional[str] = None


class NameValue(msgspec.Struct, omit_defaults=True):
    name: str
    value: str


class UserExec(msgspec.Struct, omit_defaults=True):
    apiVersion: str
    command: str
    env: Optional[List[NameValue]] = None
    args: Optional[List[str]] = None
    installHint: Optional[str] = None


class User(msgspec.Struct, omit_defaults=True):
    exec: Optional[UserExec] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    token_file: Optional[str] = msgspec.field(name="tokenFile", default=None)
    auth_provider: Optional[Dict] = msgspec.field(name="auth-provider", default=None)
    client_cert: Optional[str] = msgspec.field(name="client-certificate", default=None)
    client_cert_data: Optional[str] = msgspec.field(name="client-certificate-data", default=None)
    client_key: Optional[str] = msgspec.field(name="client-key", default=None)
    client_key_data: Optional[str] = msgspec.field(name="client-key-data", default=None)


class Cluster(msgspec.Struct, omit_defaults=True):
    """
    Attributes:
      server: the server name
    """

    server: str = "http://localhost:8080"
    certificate_auth: Optional[str] = msgspec.field(name="certificate-authority", default=None)
    certificate_auth_data: Optional[str] = msgspec.field(name="certificate-authority-data", default=None)
    insecure: bool = msgspec.field(name="insecure-skip-tls-verify", default=False)
