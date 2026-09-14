"""Extension lies; magic bytes do not. Both are needed, and a disagreement is reported."""

from pathlib import Path

import pytest

from media_mcp.sniff import sniff

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452")
JPEG = bytes.fromhex("ffd8ffe000104a46494600")
GIF = b"GIF89a" + b"\x00" * 16
PDF = b"%PDF-1.7\n" + b"\x00" * 16
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 8


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_extension_alone_is_enough_for_a_plain_png(tmp_path: Path):
    assert sniff(write(tmp_path, "a.png", PNG)) == ("image/png", [])


def test_magic_decides_when_the_extension_is_missing(tmp_path: Path):
    mime, warnings = sniff(write(tmp_path, "noext", PDF))
    assert mime == "application/pdf"
    assert warnings == []


def test_magic_decides_when_the_extension_lies(tmp_path: Path):
    """An .mp4 that is really a PDF must not be handed to a <video> element."""
    mime, warnings = sniff(write(tmp_path, "fake.mp4", PDF))
    assert mime == "application/pdf"
    assert len(warnings) == 1
    assert "mp4" in warnings[0]


def test_common_media_types_are_recognised(tmp_path: Path):
    assert sniff(write(tmp_path, "a.jpg", JPEG))[0] == "image/jpeg"
    assert sniff(write(tmp_path, "a.gif", GIF))[0] == "image/gif"
    assert sniff(write(tmp_path, "a.mp4", MP4))[0] == "video/mp4"
    assert sniff(write(tmp_path, "a.wav", WAV))[0] == "audio/wav"


def test_unknown_bytes_with_a_known_extension_are_trusted_but_flagged(tmp_path: Path):
    mime, warnings = sniff(write(tmp_path, "a.txt", b"hello"))
    assert mime == "text/plain"
    assert warnings == []


def test_unknown_bytes_and_unknown_extension_fall_back_to_octet_stream(tmp_path: Path):
    assert sniff(write(tmp_path, "a.bin", b"\x01\x02\x03\x04"))[0] == "application/octet-stream"
