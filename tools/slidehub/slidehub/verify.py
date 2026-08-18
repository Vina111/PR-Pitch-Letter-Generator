"""Fidelity regression: did assembly change how a page looks?

Each assembled page is rendered and compared against the reference image made
when the page was ingested. Both images come from the same renderer, so any
difference is attributable to the assembly step rather than to the renderer's
own approximations.

This is the check that makes the whole approach trustworthy at scale: nobody can
eyeball a 60-page deck every time, but everyone can act on "page 17 drifted".
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .fingerprint import (COLOR_WARN, FIDELITY_WARN, color_distance,
                          color_signature, dhash, hamming)
from .render import deck_to_pngs


@dataclass
class PageCheck:
    position: int
    source_uid: str
    distance: int
    color_delta: float
    ok: bool
    reference_png: str
    rendered_png: str

    @property
    def reason(self) -> str:
        if self.ok:
            return ""
        if self.distance > FIDELITY_WARN and self.color_delta > COLOR_WARN:
            return "layout+colour"
        return "layout" if self.distance > FIDELITY_WARN else "colour"


@dataclass
class FidelityReport:
    checks: list[PageCheck]
    threshold: int = FIDELITY_WARN
    color_threshold: float = COLOR_WARN

    @property
    def pages(self) -> int:
        return len(self.checks)

    @property
    def failures(self) -> list[PageCheck]:
        return [c for c in self.checks if not c.ok]

    @property
    def exact(self) -> int:
        return sum(1 for c in self.checks if c.distance == 0 and c.color_delta < 0.5)

    @property
    def worst(self) -> int:
        return max((c.distance for c in self.checks), default=0)

    @property
    def mean(self) -> float:
        return (sum(c.distance for c in self.checks) / len(self.checks)) if self.checks else 0.0

    @property
    def mean_color(self) -> float:
        return (sum(c.color_delta for c in self.checks) / len(self.checks)) if self.checks else 0.0

    @property
    def worst_color(self) -> float:
        return max((c.color_delta for c in self.checks), default=0.0)

    @property
    def passed(self) -> bool:
        return not self.failures


def check(assembled_pptx: Path, references, out_dir: Path,
          threshold: int = FIDELITY_WARN, color_threshold: float = COLOR_WARN,
          dpi: int = 110) -> FidelityReport:
    """references: ordered [(source_uid, reference_png_path), ...] matching the
    assembled deck's page order."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = deck_to_pngs(Path(assembled_pptx), out_dir, prefix="out", dpi=dpi)

    checks: list[PageCheck] = []
    for i, (uid, ref_png) in enumerate(references):
        if i >= len(rendered):
            checks.append(PageCheck(i + 1, uid, 64, 255.0, False,
                                    str(ref_png), "<missing>"))
            continue
        dist = hamming(dhash(ref_png), dhash(rendered[i]))
        delta = color_distance(color_signature(ref_png), color_signature(rendered[i]))
        ok = dist <= threshold and delta <= color_threshold
        checks.append(PageCheck(i + 1, uid, dist, delta, ok,
                                str(ref_png), str(rendered[i])))
    return FidelityReport(checks=checks, threshold=threshold,
                          color_threshold=color_threshold)
