"""`--selftest`: publish one real PNG through the real tool body.

Kept to one artefact so it can run on every install without becoming a wait.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .config import Config
from .tools.publish import publish

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png(width: int = 8, height: int = 8) -> bytes:
    raw = b"".join(b"\x00" + bytes([80, 140, 200]) * width for _ in range(height))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def sample_file(cfg: Config) -> Path:
    # Use render_root if it lives within an allowed root; otherwise use roots[0]
    # so the selftest file is always eligible to be published under the active config.
    target_root = cfg.render_root
    try:
        if not any(target_root.resolve(strict=False).is_relative_to(r.resolve(strict=False)) for r in cfg.roots):
            target_root = cfg.roots[0]
    except (ValueError, OSError, AttributeError):
        target_root = cfg.roots[0]

    target = target_root / "_selftest"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "selftest.png"
    path.write_bytes(_png())
    return path


def run(cfg: Config) -> int:
    path = sample_file(cfg)
    payload = publish(str(path), "自检", cfg)
    if payload.get("ok") is not True:
        print(f"FAIL: publish_file 拒绝了自己的样本：{payload}", flush=True)
        return 1
    media = payload["media"]
    if media["kind"] != "image" or not media["reference"].startswith("/"):
        print(f"FAIL: 描述符形状不对：{media}", flush=True)
        return 1
    print(f"OK: {media['name']} ({media['bytes']}B) -> {media['reference']}", flush=True)
    return 0
