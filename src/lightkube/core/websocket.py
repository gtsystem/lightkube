import io
import json
from typing import TYPE_CHECKING, BinaryIO, Iterable, NamedTuple, Optional, TypeVar, Union

import httpx

from .exceptions import ApiError

if TYPE_CHECKING:
    from .generic_client import BasicRequest

STDIN_CHANNEL: int = 0
STDOUT_CHANNEL: int = 1
STDERR_CHANNEL: int = 2
ERROR_CHANNEL: int = 3
CLOSE_STDIN: bytes = bytes([255, STDIN_CHANNEL])

T = TypeVar("T")


def first(iterable: Iterable[T], default: Optional[T] = None) -> Optional[T]:
    iterator = iter(iterable)
    return next(iterator, default)


class ExecResponse(NamedTuple):
    """
    Response from an exec command, containing stdout, stderr and exit code.

    Attributes:
        stdout: The command's stdout, if captured.
        stderr: The command's stderr, if captured.
        exit_code: The command's exit code.
    """

    stdout: Optional[Union[str, bytes]] = None
    stderr: Optional[Union[str, bytes]] = None
    exit_code: int = 0


class WebsocketDriver:
    PROTOCOLS = ("v5.channel.k8s.io", "v4.channel.k8s.io")

    def __init__(self, client: Optional[httpx.Client], br: "BasicRequest"):
        from httpx_ws import connect_ws

        self._ws = connect_ws(
            br.url,
            client,
            subprotocols=self.PROTOCOLS,
            params=br.params,
        )

    def write_stdin(self, ws, msg: Union[str, bytes, BinaryIO], close: bool = False):
        if ws.subprotocol != self.PROTOCOLS[0]:
            raise ApiError(
                status={
                    "status": "Failure",
                    "message": f"Only subprotocol {self.PROTOCOLS[0]} supports writing to stdin",
                }
            )
        stdin_channel = STDIN_CHANNEL.to_bytes()
        if hasattr(msg, "read"):
            while True:
                content = msg.read(128 * 1024)  # Read up to 128KB at a time
                if not content:
                    break
                ws.send_bytes(stdin_channel + content)
        else:
            if isinstance(msg, str):
                msg = msg.encode("utf-8")
            ws.send_bytes(stdin_channel + msg)
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
        capture_stdout = capture_stderr = False
        if stdout is True:
            stdout = io.BytesIO()
            capture_stdout = True
        if stderr is True:
            stderr = io.BytesIO()
            capture_stderr = True
        while True:
            message = ws.receive_bytes()
            channel, message = message[0], message[1:]
            print(channel, len(message))
            if channel == STDOUT_CHANNEL:
                if stdout:
                    stdout.write(message)
            elif channel == STDERR_CHANNEL:
                if stderr:
                    stderr.write(message)
            elif channel == ERROR_CHANNEL:
                exit_code = 0
                error = ApiError(status=json.loads(message))
                if error.status.status == "Failure":
                    if error.status.reason != "NonZeroExitCode" or raise_on_error:
                        raise error
                    details = error.status.details
                    if details and details.causes:
                        exit_code = first((int(cause.message) for cause in details.causes if cause.reason == "ExitCode"), -1)

                stdout_value = stderr_value = None
                if capture_stdout:
                    stdout_value = stdout.getvalue() if decode is None else stdout.getvalue().decode(decode)
                if capture_stderr:
                    stderr_value = stderr.getvalue() if decode is None else stderr.getvalue().decode(decode)
                return ExecResponse(stdout=stdout_value, stderr=stderr_value, exit_code=exit_code)


class AsyncWebsocketDriver:
    PROTOCOLS = ("v5.channel.k8s.io", "v4.channel.k8s.io")

    def __init__(self, client: Optional[httpx.AsyncClient], br: "BasicRequest"):
        from httpx_ws import aconnect_ws

        self._ws = aconnect_ws(
            br.url,
            client,
            subprotocols=self.PROTOCOLS,
            params=br.params,
        )

    async def write_stdin(self, ws, msg: Union[str, bytes, BinaryIO], close: bool = False):
        if ws.subprotocol != self.PROTOCOLS[0]:
            raise ApiError(
                status={
                    "status": "Failure",
                    "message": f"Only subprotocol {self.PROTOCOLS[0]} supports writing to stdin",
                }
            )
        stdin_channel = STDIN_CHANNEL.to_bytes()
        if hasattr(msg, "read"):
            while True:
                content = msg.read(128 * 1024)  # Read up to 128KB at a time
                if not content:
                    break
                await ws.send_bytes(stdin_channel + content)
        else:
            if isinstance(msg, str):
                msg = msg.encode("utf-8")
            await ws.send_bytes(stdin_channel + msg)
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
        capture_stdout = capture_stderr = False
        if stdout is True:
            stdout = io.BytesIO()
            capture_stdout = True
        if stderr is True:
            stderr = io.BytesIO()
            capture_stderr = True
        while True:
            message = await ws.receive_bytes()
            channel, message = message[0], message[1:]
            if channel == STDOUT_CHANNEL:
                if stdout:
                    stdout.write(message)
            elif channel == STDERR_CHANNEL:
                if stderr:
                    stderr.write(message)
            elif channel == ERROR_CHANNEL:
                exit_code = 0
                error = ApiError(status=json.loads(message))
                if error.status.status == "Failure":
                    if error.status.reason != "NonZeroExitCode" or raise_on_error:
                        raise error
                    details = error.status.details
                    if details and details.causes:
                        exit_code = first((int(cause.message) for cause in details.causes if cause.reason == "ExitCode"), -1)

                stdout_value = stderr_value = None
                if capture_stdout:
                    stdout_value = stdout.getvalue() if decode is None else stdout.getvalue().decode(decode)
                if capture_stderr:
                    stderr_value = stderr.getvalue() if decode is None else stderr.getvalue().decode(decode)

                return ExecResponse(stdout=stdout_value, stderr=stderr_value, exit_code=exit_code)
