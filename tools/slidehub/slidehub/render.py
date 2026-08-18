"""Rasterise decks through LibreOffice.

Every page the system stores gets a PNG: thumbnails for browsing, and — the part
that matters for this spike — a reference image the assembled output can be
checked against.

Note the property that makes that check trustworthy: both sides of the comparison
go through the same renderer, so LibreOffice's own imperfect PPTX rendering
cancels out. A difference in the result means the *file* changed, not that the
renderer is imprecise.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF


class RenderError(RuntimeError):
    pass


def _soffice() -> str:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise RenderError(
            "LibreOffice not found. Install it (apt install libreoffice-impress) — "
            "the fidelity check cannot run without a renderer."
        )
    return exe


def deck_to_pdf(pptx_path: Path, out_dir: Path, timeout: int = 180) -> Path:
    pptx_path, out_dir = Path(pptx_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # A private profile per invocation; LibreOffice refuses to run two instances
    # against one profile, which would otherwise serialise or fail the batch.
    with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile:
        cmd = [
            _soffice(),
            "-env:UserInstallation=file://%s" % profile,
            "--headless", "--norestore", "--invisible", "--nolockcheck",
            "--convert-to", "pdf:impress_pdf_Export",
            "--outdir", str(out_dir), str(pptx_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              env={**os.environ, "HOME": profile})
    pdf = out_dir / (pptx_path.stem + ".pdf")
    if not pdf.exists():
        raise RenderError(
            "LibreOffice produced no PDF for %s\nstdout: %s\nstderr: %s"
            % (pptx_path.name, proc.stdout.decode()[-800:], proc.stderr.decode()[-800:])
        )
    return pdf


def pdf_to_pngs(pdf_path: Path, out_dir: Path, prefix: str = "page",
                dpi: int = 110) -> list[Path]:
    pdf_path, out_dir = Path(pdf_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            out = out_dir / ("%s_%03d.png" % (prefix, i))
            pix.save(str(out))
            written.append(out)
    return written


def deck_to_pngs(pptx_path: Path, out_dir: Path, prefix: str = "page",
                 dpi: int = 110) -> list[Path]:
    with tempfile.TemporaryDirectory(prefix="lo-pdf-") as tmp:
        pdf = deck_to_pdf(Path(pptx_path), Path(tmp))
        return pdf_to_pngs(pdf, Path(out_dir), prefix=prefix, dpi=dpi)
