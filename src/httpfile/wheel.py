"""
???
"""

import re
from dataclasses import dataclass

from .httpfile import HttpFileRequest, Url
from .zipfile import Context as ZipFileContext
from .zipfile import ZipFileExtractionRequest, ZipMemberNameMatcher


@dataclass(frozen=True)
class WheelMetadataRequest:
    url: Url


@dataclass(frozen=True)
class WheelMetadataContents:
    contents: bytes


@dataclass(frozen=True)
class WheelContext:
    zip_context: ZipFileContext = ZipFileContext()

    # TODO: ???
    _METADATA_PATTERN = ZipMemberNameMatcher(
        re.compile(b"[a-zA-Z][^/]+?.dist-info/METADATAPK", flags=re.IGNORECASE,)
    )

    def extract_wheel_metadata(
        self, request: WheelMetadataRequest
    ) -> WheelMetadataContents:
        url = request.url
        http_file = self.zip_context.http_context.head(HttpFileRequest(url))
        contents = self.zip_context.extract_zip_member_shallow(
            ZipFileExtractionRequest(
                http_file=http_file, member_pattern=self._METADATA_PATTERN,
            )
        )
        return WheelMetadataContents(contents)
