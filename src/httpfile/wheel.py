"""
???
"""

import re
from dataclasses import dataclass

from .httpfile import HttpFileRequest, Url
from .zipfile import Context as ZipFileContext
from .zipfile import ZipFileExtractionRequest, ZipMemberNameMatcher


@dataclass(frozen=True)
class ProjectName:
    name: str


@dataclass(frozen=True)
class WheelMetadataRequest:
    url: Url
    project_name: ProjectName


@dataclass(frozen=True)
class WheelMetadataContents:
    contents: bytes


@dataclass(frozen=True)
class Context:
    zip_context: ZipFileContext = ZipFileContext()

    @classmethod
    def _create_metadata_pattern(
        cls, project_name: ProjectName
    ) -> ZipMemberNameMatcher:
        sanitized_requirement_name = project_name.name.lower().replace("-", "_")
        return ZipMemberNameMatcher(
            re.compile(
                f"{sanitized_requirement_name}[^/]+?.dist-info/METADATAPK".encode(),
                flags=re.IGNORECASE,
            )
        )

    def extract_wheel_metadata(
        self, request: WheelMetadataRequest
    ) -> WheelMetadataContents:
        url = request.url
        http_file = self.zip_context.http_context.head(HttpFileRequest(url))

        metadata_pattern = self._create_metadata_pattern(request.project_name)
        contents = self.zip_context.extract_zip_member_shallow(
            ZipFileExtractionRequest(
                http_file=http_file, member_pattern=metadata_pattern,
            )
        )
        return WheelMetadataContents(contents)
