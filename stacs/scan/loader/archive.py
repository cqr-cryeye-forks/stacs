"""Defines handlers for unpacking of archives.

SPDX-License-Identifier: BSD-3-Clause
"""

import bz2
import gzip
import hashlib
import lzma
import os
import shutil
import tarfile
import zipfile

from stacs.scan.constants import CHUNK_SIZE
from stacs.scan.exceptions import FileAccessException, InvalidFileException


def path_hash(filepath: str) -> str:
    """Returns a hash of the filepath, for use with unique directory creation."""
    return hashlib.md5(bytes(filepath, "utf-8")).hexdigest()


def zip_handler(filepath: str, directory: str) -> None:
    """Attempts to extract the provided archive."""
    try:
        os.mkdir(directory, mode=0o700)
    except OSError as err:
        raise FileAccessException(
            f"Unable to create unpack directory at {directory}: {err}"
        )

    # Attempt to unpack the zipfile to the new unpack directory.
    try:
        with zipfile.ZipFile(filepath, "r") as archive:
            archive.extractall(directory)
    except zipfile.BadZipFile as err:
        raise InvalidFileException(
            f"Unable to extract archive {filepath} to {directory}: {err}"
        )


def tar_handler(filepath: str, directory: str) -> None:
    """Attempts to extract the provided archive."""
    try:
        os.mkdir(directory, mode=0o700)
    except OSError as err:
        raise FileAccessException(
            f"Unable to create unpack directory at {directory}: {err}"
        )

    # Attempt to unpack the tarball to the new unpack directory.
    try:
        with tarfile.open(filepath, "r") as archive:
            archive.extractall(directory)
    except tarfile.TarError as err:
        raise InvalidFileException(
            f"Unable to extract archive {filepath} to {directory}: {err}"
        )


def gzip_handler(filepath: str, directory: str) -> None:
    """Attempts to extract the provided archive."""
    output = ".".join(os.path.basename(filepath).split(".")[:-1])

    # Ensure that files with a proceeding dot are properly handled.
    if len(output) < 1:
        output = os.path.basename(filepath).lstrip(".")

    # Although gzip files cannot contain more than one file, we'll still spool into
    # a subdirectory under the cache for consistency.
    try:
        os.mkdir(directory, mode=0o700)
    except OSError as err:
        raise FileAccessException(
            f"Unable to create unpack directory at {directory}: {err}"
        )

    # TODO: This can likely be optimized for tgz files, as currently the file will be
    #       first processed and gunzipped, and then reprocessed to be extracted.
    try:
        with gzip.open(filepath, "rb") as fin:
            with open(os.path.join(directory, output), "wb") as fout:
                shutil.copyfileobj(fin, fout, CHUNK_SIZE)
    except gzip.BadGzipFile as err:
        raise InvalidFileException(
            f"Unable to extract archive {filepath} to {output}: {err}"
        )


def bzip2_handler(filepath: str, directory: str) -> None:
    """Attempts to extract the provided archive."""
    output = ".".join(os.path.basename(filepath).split(".")[:-1])

    # Like gzip, bzip2 cannot support more than a single file. Again, we'll spool into
    # a subdirectory for consistency.
    try:
        os.mkdir(directory, mode=0o700)
    except OSError as err:
        raise FileAccessException(
            f"Unable to create unpack directory at {directory}: {err}"
        )

    # TODO: This can likely be optimized for tbz files, as currently the file will be
    #       first processed and gunzipped, and then reprocessed to be extracted.
    try:
        with bz2.open(filepath, "rb") as fin:
            with open(os.path.join(directory, output), "wb") as fout:
                shutil.copyfileobj(fin, fout, CHUNK_SIZE)
    except ValueError as err:
        raise InvalidFileException(
            f"Unable to extract archive {filepath} to {output}: {err}"
        )


def lzma_handler(filepath: str, directory: str) -> None:
    """Attempts to extract the provided archive."""
    output = ".".join(os.path.basename(filepath).split(".")[:-1])

    # Ensure that files with a proceeding dot are properly handled.
    if len(output) < 1:
        output = os.path.basename(filepath).lstrip(".")

    # Although xz files cannot contain more than one file, we'll still spool into
    # a subdirectory under the cache for consistency.
    try:
        os.mkdir(directory, mode=0o700)
    except OSError as err:
        raise FileAccessException(
            f"Unable to create unpack directory at {directory}: {err}"
        )

    try:
        with lzma.open(filepath, "rb") as fin:
            with open(os.path.join(directory, output), "wb") as fout:
                shutil.copyfileobj(fin, fout, CHUNK_SIZE)
    except lzma.LZMAError as err:
        raise InvalidFileException(
            f"Unable to extract archive {filepath} to {output}: {err}"
        )


def get_mimetype(chunk: bytes) -> str:
    """Attempts to locate the appropriate handler for a given file.

    This may fail if the required "magic" is at an offset greater than the CHUNK_SIZE.
    However, currently this is not an issue, but may need to be revisited later as more
    archive types are supported.
    """
    for name, options in MIME_TYPE_HANDLERS.items():
        offset = options["offset"]
        magic = options["magic"]

        for candidate in magic:
            if chunk[offset : (offset + len(candidate))] == candidate:  # noqa: E203
                return name

    return None


# Define all supported archives and their handlers. As we currently only support a small
# list of types we can just define file magic directly here, rather than use an external
# library. This removes the need for dependencies which may have other system
# dependencies - such as libmagic. It should also provide a small a speed up during
# unpacking, as we're only looking for a small number of types.
MIME_TYPE_HANDLERS = {
    "application/x-tar": {
        "offset": 257,
        "magic": [
            bytearray([0x75, 0x73, 0x74, 0x61, 0x72]),
        ],
        "handler": tar_handler,
    },
    "application/gzip": {
        "offset": 0,
        "magic": [
            bytearray([0x1F, 0x8B]),
        ],
        "handler": gzip_handler,
    },
    "application/x-bzip2": {
        "offset": 0,
        "magic": [
            bytearray([0x42, 0x5A, 0x68]),
        ],
        "handler": bzip2_handler,
    },
    "application/zip": {
        "offset": 0,
        "magic": [
            bytearray([0x50, 0x4B, 0x03, 0x04]),
            bytearray([0x50, 0x4B, 0x05, 0x06]),
            bytearray([0x50, 0x4B, 0x07, 0x08]),
        ],
        "handler": zip_handler,
    },
    "application/x-xz": {
        "offset": 0,
        "magic": [
            bytearray([0xFD, 0x37, 0x7A, 0x58, 0x5A, 0x00]),
        ],
        "handler": lzma_handler,
    },
}
