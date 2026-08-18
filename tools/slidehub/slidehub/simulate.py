"""Stand in for what a person does to a deck between export and re-upload.

The round-trip claim is only worth as much as the edits it survives, so the
spike applies the ones that actually happen after a client meeting — including
the two that break naive implementations: a reordered page, and a page whose
origin marker is gone because it was rebuilt from scratch.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from . import marker
from .pptx_compat import add_slide


def _sld_ids(prs):
    return list(prs.slides._sldIdLst)


def edit_text(prs, position: int, suffix: str) -> str:
    slide = prs.slides[position - 1]
    for shape in slide.shapes:
        if shape.has_text_frame and shape.text_frame.text.strip():
            para = shape.text_frame.paragraphs[0]
            if para.runs:
                para.runs[0].text = para.runs[0].text + suffix
                return "page %d: text edited" % position
    return "page %d: no editable text found" % position


def delete(prs, position: int) -> str:
    sldIdLst = prs.slides._sldIdLst
    sldId = _sld_ids(prs)[position - 1]
    prs.part.drop_rel(sldId.rId)
    sldIdLst.remove(sldId)
    return "page %d: deleted" % position


def strip_marker(prs, position: int) -> str:
    slide = prs.slides[position - 1]
    for shape in list(slide.shapes):
        if (shape.name or "").startswith(marker.PREFIX + marker.SEP):
            shape._element.getparent().remove(shape._element)
            return "page %d: origin marker stripped" % position
    return "page %d: no marker to strip" % position


def move(prs, position: int, to_position: int) -> str:
    sldIdLst = prs.slides._sldIdLst
    sldId = _sld_ids(prs)[position - 1]
    sldIdLst.remove(sldId)
    sldIdLst.insert(to_position - 1, sldId)
    return "page %d: moved to position %d" % (position, to_position)


def add_new(prs, title: str) -> str:
    layout = min(prs.slide_masters[0].slide_layouts,
                 key=lambda lo: len(lo.placeholders))
    # Not prs.slides.add_slide — see pptx_compat: after a delete it reuses an
    # occupied package path and silently corrupts the file.
    slide = add_slide(prs, layout)
    box = slide.shapes.add_textbox(Inches(1), Inches(2.4),
                                   prs.slide_width - Inches(2), Inches(2))
    tf = box.text_frame
    tf.word_wrap = True
    tf.text = title
    tf.paragraphs[0].runs[0].font.size = Pt(30)
    p = tf.add_paragraph()
    p.text = "汇报现场临时补的一页，库里没有对应模块"
    p.runs[0].font.size = Pt(16)
    return "appended a brand-new page"


def client_meeting(src: Path, out: Path) -> list[str]:
    """The realistic edit set, applied in an order that keeps positions stable."""
    prs = Presentation(str(src))
    log = [
        edit_text(prs, 2, "（客户要求改口径）"),
        strip_marker(prs, 7),
        move(prs, 10, 1),
        delete(prs, 5),
        add_new(prs, "补充：下阶段排期建议"),
    ]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return log
