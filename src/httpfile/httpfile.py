"""
???
"""

from dataclasses import dataclass
from typing import Optional, Text, Union

import requests


def _get_url_scheme(url: Union[str, Text]) -> Optional[Text]:
    if ":" not in url:
        return None
    return url.split(":", 1)[0].lower()


@dataclass(frozen=True)
class Url:
    url: str

    def __post_init__(self) -> None:
        scheme = _get_url_scheme(self.url)
        assert scheme in ["http", "https"]


@dataclass(frozen=True)
class HttpFileRequest:
    url: Url


@dataclass(frozen=True)
class Size:
    size: int = 0

    def __post_init__(self) -> None:
        assert self.size >= 0

    def __add__(self, other) -> "Size":
        return Size(self.size + other.size)

    def __sub__(self, other) -> "Size":
        return Size(self.size - other.size)

    def __lt__(self, other) -> bool:
        return self.size < other.size

    def __le__(self, other) -> bool:
        return self.size <= other.size

    def __gt__(self, other) -> bool:
        return self.size > other.size

    def __ge__(self, other) -> bool:
        return self.size >= other.size


@dataclass(frozen=True)
class ByteRange:
    start: Size
    end: Size

    def __post_init__(self) -> None:
        assert self.end >= self.start

    def as_bytes_range_header(self) -> str:
        return f"bytes={self.start.size}-{self.end.size}"

    def size_diff(self) -> Size:
        return self.end - self.start


@dataclass(frozen=True)
class BytesRangeRequest:
    start: Optional[Size]
    end: Optional[Size]

    def __post_init__(self) -> None:
        if (self.start is not None) and (self.end is not None):
            assert self.end >= self.start

    def get_byte_range(self, size: Size) -> ByteRange:
        if self.start is None:
            start = 0
        else:
            assert self.start <= size
            start = self.start.size

        if self.end is None:
            end = size.size
        else:
            assert self.end <= size
            end = self.end.size

        return ByteRange(start=Size(start), end=Size(end))


@dataclass(frozen=True)
class HttpFile:
    url: Url
    size: Size


@dataclass(frozen=True)
class Context:
    session: requests.Session = requests.Session()

    def head(self, request: HttpFileRequest) -> HttpFile:
        resp = self.session.head(request.url.url)
        resp.raise_for_status()
        assert "bytes" in resp.headers["Accept-Ranges"]
        content_length = int(resp.headers["Content-Length"])
        return HttpFile(url=request.url, size=Size(content_length))

    def range_request(self, http_file: HttpFile, request: BytesRangeRequest) -> bytes:
        byte_range = request.get_byte_range(http_file.size)
        resp = self.session.get(
            http_file.url.url, headers={"Range": byte_range.as_bytes_range_header()}
        )
        resp.raise_for_status()

        if Size(len(resp.content)) == http_file.size:
            # This request for the full URL contents is cached, and we should return just the
            # requested byte range.
            start = byte_range.start.size
            end = byte_range.end.size
            response_bytes = resp.content[start:end]
        else:
            response_bytes = resp.content

        size_diff = byte_range.size_diff()
        assert Size(len(response_bytes)) == size_diff
        return response_bytes
