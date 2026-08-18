"""Split a deck into self-contained single-slide .pptx files.

Strategy: copy the whole package, then drop every slide but one. That keeps the
slide masters, layouts, theme and media byte-identical to the source, so a split
page renders exactly like the page it came from. It costs some duplicated master
XML per page (tens of KB) which is a good trade against fidelity; media is the
part that actually dominates size and it gets deduplicated by hash downstream.

The alternative — building a fresh minimal package per slide — is smaller but
re-derives the theme, which is exactly the risk this project cannot take.
"""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation

@dataclass
class SlideRecord:
    index: int
    pptx_path: Path
    text: str
    notes: str
    shape_kinds: list[str] = field(default_factory=list)
    geometry: list[tuple] = field(default_factory=list)
    media_sha: list[str] = field(default_factory=list)
    layout_name: str = ""
    has_chart: bool = False
    has_table: bool = False
    has_group: bool = False
    has_smartart: bool = False


def _keep_only(prs, keep_idx: int) -> None:
    sldIdLst = prs.slides._sldIdLst
    for j, sldId in enumerate(list(sldIdLst)):
        if j == keep_idx:
            continue
        prs.part.drop_rel(sldId.rId)
        sldIdLst.remove(sldId)


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _is_group(shape) -> bool:
    """Test the element tag rather than shape_type: python-pptx raises on shapes
    it cannot classify, and real decks are full of those."""
    return shape.element.tag == "{%s}grpSp" % P_NS


def _kind(shape) -> str:
    try:
        st = shape.shape_type
    except (NotImplementedError, ValueError, KeyError):
        return "UNKNOWN"
    if st is None:
        return "NONE"
    return str(st).split(" ")[0]


def _walk(shapes):
    """Yield every shape, descending into groups."""
    for sh in shapes:
        yield sh
        if _is_group(sh):
            yield from _walk(sh.shapes)


def _harvest(slide, rec: SlideRecord) -> None:
    texts: list[str] = []
    for sh in _walk(slide.shapes):
        kind = _kind(sh)
        rec.shape_kinds.append(kind)

        # Geometry on a 24x24 grid — coarse enough to survive nudges, fine
        # enough to distinguish genuinely different layouts.
        try:
            if None not in (sh.left, sh.top, sh.width, sh.height):
                rec.geometry.append(
                    (kind, round(sh.left / 400000), round(sh.top / 400000),
                     round(sh.width / 400000), round(sh.height / 400000))
                )
        except (AttributeError, TypeError, ValueError):
            pass

        if sh.has_text_frame and sh.text_frame.text.strip():
            texts.append(sh.text_frame.text.strip())
        if getattr(sh, "has_table", False):
            rec.has_table = True
            for row in sh.table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        texts.append(cell.text.strip())
        if getattr(sh, "has_chart", False):
            rec.has_chart = True
            try:
                if sh.chart.has_title and sh.chart.chart_title.has_text_frame:
                    texts.append(sh.chart.chart_title.text_frame.text.strip())
            except (AttributeError, ValueError):
                pass
        if _is_group(sh):
            rec.has_group = True
        if kind == "PICTURE":
            try:
                rec.media_sha.append(hashlib.sha256(sh.image.blob).hexdigest())
            except (AttributeError, ValueError):
                pass
        # SmartArt surfaces as a graphicFrame carrying a diagram relationship.
        if sh.element.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/diagram}relIds"):
            rec.has_smartart = True

    rec.text = "\n".join(texts)
    if slide.has_notes_slide:
        rec.notes = slide.notes_slide.notes_text_frame.text.strip()
    try:
        rec.layout_name = slide.slide_layout.name
    except (AttributeError, KeyError):
        rec.layout_name = ""


def split_deck(src_path: Path, out_dir: Path) -> list[SlideRecord]:
    src_path, out_dir = Path(src_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    n_slides = len(Presentation(str(src_path)).slides)
    work = out_dir / "_work.pptx"
    records: list[SlideRecord] = []

    for i in range(n_slides):
        shutil.copyfile(src_path, work)
        prs = Presentation(str(work))
        _keep_only(prs, i)
        out = out_dir / ("p%03d.pptx" % (i + 1))
        prs.save(str(out))

        rec = SlideRecord(index=i + 1, pptx_path=out, text="", notes="")
        _harvest(Presentation(str(out)).slides[0], rec)
        records.append(rec)

    work.unlink(missing_ok=True)
    return records
