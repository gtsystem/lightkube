from typing import Dict, List
from dataclasses import dataclass, field
import tempfile
import base64

from ..core.dataclasses_dict import DataclassDictMixIn


class FileStr(str):
    def __new__(cls, data):
        if data is None:
            return None

        f = tempfile.NamedTemporaryFile()
        f.write(base64.b64decode(data))
        f.flush()
        file = str.__new__(cls, f.name)
        file.handler = f
        return file

    def __del__(self):
        if self.handler:
            self.handler.close()
            self.handler = None


@dataclass
class Context(DataclassDictMixIn):
    cluster: str
    user: str = None
    namespace: str = None


@dataclass
class NameValue(DataclassDictMixIn):
    name: str
    value: str


@dataclass
class UserExec(DataclassDictMixIn):
    apiVersion: str
    command: str = None
    env: List[NameValue] = field(default_factory=list)
    args: List[str] = field(default_factory=list)
    installHint: str = None


@dataclass
class User(DataclassDictMixIn):
    exec: UserExec = None
    username: str = None
    password: str = None
    token: str = None
    auth_provider: Dict = field(metadata={'json': 'auth-provider'}, default=None)
    client_cert: str = field(metadata={'json': 'client-certificate'}, default=None)
    client_cert_data: str = field(metadata={'json': 'client-certificate-data'}, default=None)
    client_key: str = field(metadata={'json': 'client-key'}, default=None)
    client_key_data: str = field(metadata={'json': 'client-key-data'}, default=None)


@dataclass
class Cluster(DataclassDictMixIn):
    server: str = "http://localhost:8080"
    certificate_auth: str = field(metadata={'json': 'certificate-authority'}, default=None)
    certificate_auth_data: str = field(metadata={'json': 'certificate-authority-data'}, default=None)
    insecure: bool = field(metadata={'json': 'insecure-skip-tls-verify'}, default=False)
