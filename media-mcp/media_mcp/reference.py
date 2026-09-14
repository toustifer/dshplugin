"""Build the `/`-rooted reference the Host can resolve.

Measured with `node:path.resolve` on this machine, `cwd = D:\\myprogram\\dshplugin`:

    resolve(cwd, '/a/b.mp4')        -> 'D:\\a\\b.mp4'          (misses)
    resolve(cwd, '/D:/a/b.mp4')     -> 'D:\\D:\\a\\b.mp4'      (misses)
    resolve(cwd, '/myprogram/dshplugin/a/b.mp4') -> the file   (hits)

For a `/`-rooted argument `resolve` discards the cwd's directories entirely and keeps
only its DRIVE. So the reference is the absolute path minus the drive letter, and the
`fs` provider's cwd only has to sit on the same drive.
"""

from __future__ import annotations

import re
from pathlib import Path

DRIVE_RE = re.compile(r"^([A-Za-z]):(/.*)$")
# Whitespace and these characters break Markdown destinations or URL encoding.
UNSAFE_RE = re.compile(r"[\s()<>\"'\u4e00-\u9fff]")


def rooted_reference(absolute_posix: str) -> str | None:
    if UNSAFE_RE.search(absolute_posix):
        return None
    match = DRIVE_RE.match(absolute_posix)
    if match is not None:
        return match.group(2)
    if absolute_posix.startswith("/") and not absolute_posix.startswith("//"):
        return absolute_posix
    return None


def reference_for(path: Path) -> str | None:
    """`None` when no same-origin form exists — never a reference that would 404."""
    if not path.is_absolute():
        return None
    try:
        absolute = path.resolve(strict=False)
    except OSError:
        return None
    return rooted_reference(absolute.as_posix())
