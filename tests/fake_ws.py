import json
from typing import Optional


class _AwaitableResult:
    __slots__ = ("_value",)

    def __init__(self, value) -> None:
        self._value = value

    def __await__(self):
        if False:  # needed to make this a generator function
            yield None
        return self._value


class _AwaitableBytes(_AwaitableResult):
    def __getitem__(self, key):
        return self._value[key]

    def __len__(self) -> int:
        return len(self._value)

    def __iter__(self):
        return iter(self._value)

    def __bytes__(self) -> bytes:
        return self._value


class FakeWS:
    subprotocol = "v5.channel.k8s.io"

    def __init__(self, messages, exit_code: int = 0):
        # messages: list of (channel, payload) tuples
        self._messages = []
        for ch, payload in messages:
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            self._messages.append(bytes([ch]) + payload)
        # append an ERROR channel status message reflecting exit_code
        status: dict[str, object]
        if exit_code == 0:
            status = {"status": "Success"}
        else:
            status = {
                "status": "Failure",
                "reason": "NonZeroExitCode",
                "details": {"causes": [{"reason": "ExitCode", "message": str(exit_code)}]},
                "message": "command exited",
            }
        self._messages.append(bytes([3]) + json.dumps(status).encode("utf-8"))
        self.sent: list[bytes] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def receive_bytes(self, timeout: Optional[float] = None):
        return _AwaitableBytes(self._messages.pop(0))

    def send_bytes(self, data):
        self.sent.append(data)
        return _AwaitableResult(None)

    @staticmethod
    def make_connect(messages, exit_code: int = 0):
        def _connect(url, client, subprotocols, params):
            return FakeWS(messages, exit_code)

        return _connect

    def as_connect(self):
        def _connect(url, client, subprotocols, params):
            return self

        return _connect
