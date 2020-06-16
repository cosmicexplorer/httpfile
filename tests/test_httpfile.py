"""
???
"""

from httpfile.httpfile import (BytesRangeRequest, Context, HttpFile,
                               HttpFileRequest, Size, Url)

from .util import StubHandler, http_server


class FileHandler(StubHandler):
    _response_text = "this is the file contents"
    _response_path = "/some-path"


context = Context()


def test_http_range():
    with http_server(FileHandler) as port:
        url = Url(f"http://localhost:{port}/some-path")
        req = HttpFileRequest(url)
        expected = HttpFile(url=url, size=Size(len(FileHandler._response_text)))
        assert context.head(req) == expected

        get_whole_file = BytesRangeRequest(start=None, end=None)
        contents = context.range_request(expected, get_whole_file)
        assert contents == FileHandler._response_text.encode()

        half_extent = len(FileHandler._response_text) // 2
        get_half_file = BytesRangeRequest(start=None, end=Size(half_extent))
        half_contents = context.range_request(expected, get_half_file)
        assert half_contents == FileHandler._response_text[:half_extent].encode()
