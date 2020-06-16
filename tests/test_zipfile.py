"""
???
"""

import re
import zipfile
from pathlib import Path

from httpfile.httpfile import HttpFileRequest
from httpfile.zipfile import (Context, ZipFileExtractionRequest,
                              ZipMemberNameMatcher)

from .util import serve_zip

context = Context()


def test_extract_file_from_deflated_zip():
    with serve_zip(
        Path("asdf.txt"), b"asdf\n", compression=zipfile.ZIP_DEFLATED
    ) as url:
        req = HttpFileRequest(url)
        http_file = context.http_context.head(req)

        zip_req = ZipFileExtractionRequest(
            http_file=http_file,
            member_pattern=ZipMemberNameMatcher(re.compile(b"asdf.txtPK")),
        )
        zip_member = context.extract_zip_member_shallow(zip_req)
        assert zip_member == b"asdf\n"
