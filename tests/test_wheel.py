from textwrap import dedent

from httpfile.wheel import (Context, ProjectName, WheelMetadataContents,
                            WheelMetadataRequest)

from .util import serve_wheel

context = Context()


def test_extract_metadata_from_wheel():
    name = ProjectName("asdf")
    with serve_wheel(name, version="0.0.1") as url:
        wheel_req = WheelMetadataRequest(url, project_name=name,)

        metadata_contents = context.extract_wheel_metadata(wheel_req)
        assert metadata_contents == WheelMetadataContents(
            dedent(
                """\
            Metadata-Version: 2.1
            Name: asdf
            Version: 0.0.1
            Summary: UNKNOWN
            Home-page: UNKNOWN
            Author: UNKNOWN
            Author-email: UNKNOWN
            License: UNKNOWN
            Platform: UNKNOWN
            Requires-Dist: requests

            UNKNOWN


            """
            ).encode()
        )
