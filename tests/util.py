import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from queue import Queue
from socketserver import TCPServer
from textwrap import dedent
from typing import Iterator, List, Type

from httpfile.httpfile import Url
from httpfile.wheel import ProjectName


@contextmanager
def _http_port(handler_class: Type) -> Iterator[int]:
    def serve(port_queue: "Queue[int]", shutdown_queue: "Queue[bool]") -> None:
        httpd = TCPServer(("", 0), handler_class)
        httpd.timeout = 0.1
        port_queue.put(httpd.server_address[1])
        while shutdown_queue.empty():
            httpd.handle_request()

    port_queue: "Queue[int]" = Queue()
    shutdown_queue: "Queue[bool]" = Queue()
    t = threading.Thread(target=lambda: serve(port_queue, shutdown_queue))
    t.daemon = True
    t.start()

    try:
        yield port_queue.get(block=True)
    finally:
        shutdown_queue.put(True)
        t.join()


class _StubHandler(BaseHTTPRequestHandler):
    _response_text = b""
    _response_path = "/"

    def do_HEAD(self):
        self.send_headers()

    def do_GET(self):
        self.send_headers()
        assert self._response_path.startswith("/")
        self.wfile.write(self._response_text)

    def send_headers(self):
        code = 200 if self.path == self._response_path else 404
        self.send_response(code)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", "text/utf-8")
        self.send_header("Content-Length", f"{len(self._response_text)}")
        self.end_headers()


@contextmanager
def _serve_http(handler_class: Type[_StubHandler]) -> Iterator[Url]:
    with _http_port(handler_class) as port:
        yield Url(f"http://localhost:{port}{handler_class._response_path}")


@contextmanager
def serve_file(file_contents: bytes) -> Iterator[Url]:
    class FileHandler(_StubHandler):
        _response_text = file_contents

    with _serve_http(FileHandler) as url:
        yield url


@contextmanager
def mock_zip(
    single_file_path: Path, single_file_contents: bytes, *, compression: int,
) -> Iterator[Path]:
    with temporary_file_path(Path("test.zip")) as zip_path:
        with zipfile.ZipFile(zip_path, mode="w", compression=compression) as zf:
            zf.writestr(str(single_file_path), single_file_contents)
        assert zip_path.exists()

        yield zip_path


@contextmanager
def serve_zip(
    single_file_path: Path, single_file_contents: bytes, *, compression: int,
) -> Iterator[Url]:
    with mock_zip(
        single_file_path=single_file_path,
        single_file_contents=single_file_contents,
        compression=compression,
    ) as zip_path:
        zip_contents = _read_file(zip_path)

        class ZipHandler(_StubHandler):
            _response_text = zip_contents

        with _serve_http(ZipHandler) as url:
            yield url


@contextmanager
def temporary_dir() -> Iterator[Path]:
    """A with-context that creates a temporary directory."""
    path = tempfile.mkdtemp()

    try:
        yield Path(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


@contextmanager
def temporary_file_path(filename: Path) -> Iterator[Path]:
    with temporary_dir() as td:
        yield td / filename


def _dump_file(path: Path, contents: bytes) -> None:
    with open(path, "wb") as f:
        f.write(contents)


def _read_file(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _run_python(argv: List[str], cwd: Path) -> bytes:
    return subprocess.check_output([sys.executable, *argv], cwd=cwd)


@contextmanager
def mock_wheel(name: ProjectName, *, version: str) -> Iterator[Path]:
    with temporary_dir() as td:
        _dump_file(
            td / "setup.py",
            dedent(
                """\
        from setuptools import setup
        setup()
        """
            ).encode(),
        )

        _dump_file(
            td / "setup.cfg",
            dedent(
                f"""\
        [metadata]
        name = {name.name}
        version = {version}

        [options]
        install_requires =
          requests
        """
            ).encode(),
        )

        _ = _run_python(["setup.py", "bdist_wheel"], cwd=td)
        globbed_wheel = list(td.glob("dist/*.whl"))
        assert len(globbed_wheel) == 1
        yield globbed_wheel[0]


@contextmanager
def serve_wheel(name: ProjectName, *, version: str) -> Iterator[Url]:
    with mock_wheel(name, version=version) as wheel_path:
        wheel_contents = _read_file(wheel_path)

        class WheelHandler(_StubHandler):
            _response_text = wheel_contents

        with _serve_http(WheelHandler) as url:
            yield url
