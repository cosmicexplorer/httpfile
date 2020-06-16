"""
???
"""

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
from queue import Queue
from socketserver import TCPServer
from typing import Iterator, Type


@contextmanager
def http_server(handler_class: Type) -> Iterator[int]:
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


class StubHandler(BaseHTTPRequestHandler):
    _response_text = ""
    _response_path = "/"

    def do_HEAD(self):
        self.send_headers()

    def do_GET(self):
        self.send_headers()
        self.wfile.write(self._response_text.encode())

    def send_headers(self):
        code = 200 if self.path == self._response_path else 404
        self.send_response(code)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", "text/utf-8")
        self.send_header("Content-Length", f"{len(self._response_text)}")
        self.end_headers()
