import io
import json
import queue
from time import monotonic
from typing import TYPE_CHECKING, Any, BinaryIO, ClassVar, Iterable, Optional, TypeVar, Union, overload

import httpx
from httpx_ws import aconnect_ws, connect_ws

from ..types import ExecResponse
from .exceptions import ApiError

if TYPE_CHECKING:
    from .generic_client import BasicRequest

STDIN_CHANNEL: int = 0
STDOUT_CHANNEL: int = 1
STDERR_CHANNEL: int = 2
ERROR_CHANNEL: int = 3
CLOSE_STDIN: bytes = bytes([255, STDIN_CHANNEL])

T = TypeVar("T")


@overload
def first(iterable: Iterable[T], default: None) -> Optional[T]: ...


@overload
def first(iterable: Iterable[T], default: T) -> T: ...


def first(iterable: Iterable[T], default: Optional[T] = None) -> Optional[T]:
    iterator = iter(iterable)
    return next(iterator, default)


class BudgetTimer:
    def __init__(self, timeout: Optional[float], timeout_msg: str) -> None:
        self._deadline = monotonic() + timeout if timeout is not None else None
        self._timeout_msg = timeout_msg

    def budget(self) -> Optional[float]:
        if self._deadline is None:
            return None
        budget = self._deadline - monotonic()
        if budget <= 0:
            raise httpx.ReadTimeout(self._timeout_msg)
        return budget


class BaseWebsocketDriver:
    PROTOCOLS: ClassVar[list[str]] = ["v5.channel.k8s.io", "v4.channel.k8s.io"]
    _TIMEOUT_MSG: ClassVar[str] = "Timeout while waiting complete response from exec command"
    _ws: Any

    def __init__(self, client: Union[httpx.Client, httpx.AsyncClient], br: "BasicRequest", timeout: Optional[float] = None):
        self._timeout = timeout
        ws_func = connect_ws if isinstance(client, httpx.Client) else aconnect_ws
        self._ws = ws_func(
            br.url,
            client,  # type: ignore # this is either httpx.Client or httpx.AsyncClient, both of which are accepted by the respective connect_ws function
            subprotocols=self.PROTOCOLS,
            params=br.params,
        )

    def ensure_stdin_supported(self, ws):
        if ws.subprotocol != self.PROTOCOLS[0]:
            raise ApiError(
                status={
                    "status": "Failure",
                    "message": f"Only subprotocol {self.PROTOCOLS[0]} supports writing to stdin",
                }
            )

    def chunk_stdin(self, msg: Union[str, bytes, BinaryIO], chunk_size: int = 128 * 1024) -> Iterable[bytes]:
        if hasattr(msg, "read"):
            while True:
                content = msg.read(chunk_size)
                if not content:
                    break
                yield content
        else:
            if isinstance(msg, str):
                msg = msg.encode("utf-8")
            yield msg


class WebsocketDriver(BaseWebsocketDriver):
    def write_stdin(self, ws, msg: Union[str, bytes, BinaryIO], close: bool = False):
        self.ensure_stdin_supported(ws)
        stdin_channel = STDIN_CHANNEL.to_bytes(1)
        for chunk in self.chunk_stdin(msg):
            ws.send_bytes(stdin_channel + chunk)
        if close:
            ws.send_bytes(CLOSE_STDIN)  # Close connection

    def write_and_read(
        self,
        stdin: Union[str, bytes, BinaryIO, None] = None,
        stdout: Union[BinaryIO, bool] = False,
        stderr: Union[BinaryIO, bool] = False,
        decode: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> ExecResponse:
        with self._ws as ws:
            if stdin is not None:
                self.write_stdin(ws, stdin, close=True)

            return self.read_output(ws, stdout=stdout, stderr=stderr, raise_on_error=raise_on_error, decode=decode)

    def read_output(
        self,
        ws,
        stdout: Union[BinaryIO, bool] = False,
        stderr: Union[BinaryIO, bool] = False,
        raise_on_error: bool = False,
        decode: Optional[str] = None,
    ) -> ExecResponse:
        accumulator = ExecAccumulator(stdout=stdout, stderr=stderr, raise_on_error=raise_on_error, decode=decode)
        timer = BudgetTimer(self._timeout, self._TIMEOUT_MSG)
        while True:
            budget = timer.budget()
            try:
                message = ws.receive_bytes(timeout=budget)
            except queue.Empty as e:
                raise httpx.ReadTimeout(self._TIMEOUT_MSG) from e
            channel, message = message[0], message[1:]
            response = accumulator.feed(channel, message)
            if response is not None:
                return response


class AsyncWebsocketDriver(BaseWebsocketDriver):
    async def write_stdin(self, ws, msg: Union[str, bytes, BinaryIO], close: bool = False):
        self.ensure_stdin_supported(ws)
        stdin_channel = STDIN_CHANNEL.to_bytes(1)
        for chunk in self.chunk_stdin(msg):
            await ws.send_bytes(stdin_channel + chunk)
        if close:
            await ws.send_bytes(CLOSE_STDIN)  # Close connection

    async def write_and_read(
        self,
        stdin: Union[str, bytes, BinaryIO, None] = None,
        stdout: Union[BinaryIO, bool] = False,
        stderr: Union[BinaryIO, bool] = False,
        decode: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> ExecResponse:
        async with self._ws as ws:
            if stdin is not None:
                await self.write_stdin(ws, stdin, close=True)

            return await self.read_output(ws, stdout=stdout, stderr=stderr, raise_on_error=raise_on_error, decode=decode)

    async def read_output(
        self,
        ws,
        stdout: Union[BinaryIO, bool] = False,
        stderr: Union[BinaryIO, bool] = False,
        raise_on_error: bool = False,
        decode: Optional[str] = None,
    ) -> ExecResponse:
        accumulator = ExecAccumulator(stdout=stdout, stderr=stderr, raise_on_error=raise_on_error, decode=decode)
        timer = BudgetTimer(self._timeout, self._TIMEOUT_MSG)
        while True:
            budget = timer.budget()
            try:
                message = await ws.receive_bytes(timeout=budget)
            except TimeoutError as e:
                raise httpx.ReadTimeout(self._TIMEOUT_MSG) from e
            channel, message = message[0], message[1:]
            response = accumulator.feed(channel, message)
            if response is not None:
                return response


class ExecAccumulator:
    def __init__(
        self,
        *,
        stdout: Union[BinaryIO, bool],
        stderr: Union[BinaryIO, bool],
        raise_on_error: bool,
        decode: Optional[str],
    ) -> None:
        self._raise_on_error = raise_on_error
        self._decode = decode
        self._capture_stdout = stdout is True
        self._capture_stderr = stderr is True
        self._stdout = io.BytesIO() if stdout is True else stdout
        self._stderr = io.BytesIO() if stderr is True else stderr

    def feed(self, channel: int, message: bytes) -> Optional[ExecResponse]:
        if channel == STDOUT_CHANNEL:
            if self._stdout:
                self._stdout.write(message)
            return None
        if channel == STDERR_CHANNEL:
            if self._stderr:
                self._stderr.write(message)
            return None
        if channel != ERROR_CHANNEL:
            return None

        exit_code = 0
        error = ApiError(status=json.loads(message))
        if error.status.status == "Failure":
            if error.status.reason != "NonZeroExitCode" or self._raise_on_error:
                raise error
            details = error.status.details
            if details and details.causes:
                exit_code = first(
                    (int(cause.message) for cause in details.causes if cause.reason == "ExitCode" and cause.message), -1
                )

        stdout_value = stderr_value = None
        if self._capture_stdout:
            stdout_value = self._stdout.getvalue() if self._decode is None else self._stdout.getvalue().decode(self._decode)  # type: ignore # _stdout is always BytesIO when _capture_stdout is True, so it has getvalue() method
        if self._capture_stderr:
            stderr_value = self._stderr.getvalue() if self._decode is None else self._stderr.getvalue().decode(self._decode)  # type: ignore # _stdout is always BytesIO when _capture_stderr is True, so it has getvalue() method

        return ExecResponse(stdout=stdout_value, stderr=stderr_value, exit_code=exit_code)
