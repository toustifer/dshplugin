"""`publish_file`: the whole channel in one function.

Order matters. Validation runs first and returns early, so a refusal can never mint a
reference — a reference that would 404 or 413 is worse than no reference, because the
user sees a broken card instead of a sentence explaining what to do.
"""

from __future__ import annotations

from pathlib import Path

from ..classify import classify
from ..config import Config
from ..envelope import descriptor, failure, success
from ..rasterize import rasterize
from ..reference import reference_for
from ..sniff import sniff
from ..validate import Rejection, validate


def publish(raw_path: str, title: str | None, cfg: Config) -> dict:
    rejection = validate(raw_path, cfg)
    if rejection is not None:
        return failure(rejection)

    target = Path(raw_path).resolve(strict=False)
    mime, warnings = sniff(target)
    kind = classify(mime)
    reference = reference_for(target)
    if reference is None:
        # validate() already refuses this case; reaching here means the two disagree,
        # and a disagreement must never be silently papered over with a bad reference.
        return failure(
            Rejection(
                "unreferenceable",
                f"{target} 通过了校验却算不出同源引用",
                "把文件复制到一个只用 ASCII、无空格的路径下再发布",
            )
        )

    primary = descriptor(
        target,
        reference=reference,
        kind=kind,
        mime=mime,
        title=title,
        warnings=warnings,
    )

    extras: list[dict] = []
    if kind == "pdf":
        pages, total, page_warnings = rasterize(target, cfg)
        warnings = [*warnings, *page_warnings]
        primary["warnings"] = list(warnings)
        if total is not None:
            primary["pages"] = total
        for page in pages:
            page_reference = reference_for(page)
            if page_reference is None:
                warnings.append(f"跳过无法引用的预览图 {page.name}")
                continue
            extras.append(
                descriptor(
                    page,
                    reference=page_reference,
                    kind="image",
                    mime="image/png",
                    title=None,
                    warnings=[],
                )
            )
        primary["warnings"] = list(warnings)

    return success(primary, extras=extras, warnings=warnings)
