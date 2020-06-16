"""
???
"""

import re
import struct
import zlib
from dataclasses import dataclass

from .httpfile import BytesRangeRequest
from .httpfile import Context as HttpContext
from .httpfile import HttpFile, Size


# From https://stackoverflow.com/a/1089787/2518889:
def _inflate(data):
    decompress = zlib.decompressobj(-zlib.MAX_WBITS)
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated


def _decode_4_byte_unsigned(byte_string):
    """Unpack as a little-endian unsigned long."""
    assert isinstance(byte_string, bytes) and len(byte_string) == 4
    return struct.unpack("<L", byte_string)[0]


def _decode_2_byte_unsigned(byte_string):
    """Unpack as a little-endian unsigned short."""
    assert isinstance(byte_string, bytes) and len(byte_string) == 2
    return struct.unpack("<H", byte_string)[0]


@dataclass(frozen=True)
class ZipMemberNameMatcher:
    pattern: re.Pattern

    def __post_init__(self) -> None:
        # Matching file names in zip files without the zipfile library requires a binary regex, not
        # "text".
        assert isinstance(self.pattern.pattern, bytes)


@dataclass(frozen=True)
class ZipFileExtractionRequest:
    http_file: HttpFile
    member_pattern: ZipMemberNameMatcher


@dataclass(frozen=True)
class Context:
    http_context: HttpContext = HttpContext()

    _ABSOLUTE_MINIMUM_CENTRAL_DIRECTORY_SIZE = 2000
    _CENTRAL_DIRECTORY_MAX_SIZE_FACTOR = 0.01

    @classmethod
    def _estimate_minimum_central_directory_record_size(cls, size: Size) -> Size:
        lower_bound = int(
            max(
                cls._ABSOLUTE_MINIMUM_CENTRAL_DIRECTORY_SIZE,
                size.size * cls._CENTRAL_DIRECTORY_MAX_SIZE_FACTOR,
            )
        )
        actual_record_size = min(lower_bound, size.size)
        return Size(actual_record_size)

    def extract_zip_member_shallow(self, request: ZipFileExtractionRequest) -> bytes:
        http_file = request.http_file
        full_size = http_file.size

        estimated_directory_record_size = self._estimate_minimum_central_directory_record_size(
            full_size
        )
        central_directory_range_request = BytesRangeRequest(
            start=(full_size - estimated_directory_record_size), end=full_size,
        )

        zip_tail = self.http_context.range_request(
            http_file, central_directory_range_request
        )

        filename_in_central_dir_header = request.member_pattern.pattern.search(zip_tail)

        assert filename_in_central_dir_header is not None
        matched_filename = filename_in_central_dir_header.group(0)

        filename_start = filename_in_central_dir_header.start()
        offset_start = filename_start - 4
        encoded_offset_for_local_file = zip_tail[offset_start:filename_start]
        local_file_offset = _decode_4_byte_unsigned(encoded_offset_for_local_file)

        local_file_header_range_request = BytesRangeRequest(
            start=Size(local_file_offset + 18), end=Size(local_file_offset + 30),
        )
        file_header_no_filename = self.http_context.range_request(
            http_file, local_file_header_range_request
        )

        compressed_size = _decode_4_byte_unsigned(file_header_no_filename[:4])
        uncompressed_size = _decode_4_byte_unsigned(file_header_no_filename[4:8])
        file_name_length = _decode_2_byte_unsigned(file_header_no_filename[8:10])
        assert file_name_length == (len(matched_filename) - 2)
        extra_field_length = _decode_2_byte_unsigned(file_header_no_filename[10:12])

        compressed_start = (
            local_file_offset + 30 + file_name_length + extra_field_length
        )
        compressed_end = compressed_start + compressed_size

        compressed_file_range_request = BytesRangeRequest(
            start=Size(compressed_start), end=Size(compressed_end),
        )
        compressed_file = self.http_context.range_request(
            http_file, compressed_file_range_request
        )

        uncompressed_file_contents = _inflate(compressed_file)
        assert len(uncompressed_file_contents) == uncompressed_size

        return uncompressed_file_contents
