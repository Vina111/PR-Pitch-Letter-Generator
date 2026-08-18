"""Merge single-slide decks into one deck, without touching the slides.

Each page brings its own layout, master and theme along and stays attached to
the layout it was authored under. Nothing is re-mastered, recoloured or
reflowed — the page that comes out is the page that went in.

The output carries one master set per distinct source deck. That is the cost,
and it is the right one to pay: the alternative is rewriting every page onto a
shared master, which means resolving theme colours, baking inherited text
styles and injecting chart palettes — editing the slide, in other words, with a
new class of visual bug behind every step. Measured side by side on decks with
three different themes, this approach renders bit-identical to the source while
the re-mastering one does not.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.parts.slide import SlidePart

from . import manifest, marker
from .opc import PartCloner, remap_rids
from .pptx_compat import free_partname

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


@dataclass
class AssemblyReport:
    slides: int = 0
    parts_cloned: int = 0
    rels_rewritten: int = 0
    masters_added: int = 0
    size_mismatches: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _strip_slides(prs) -> None:
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst):
        prs.part.drop_rel(sldId.rId)
        sldIdLst.remove(sldId)


def _register_master(prs, master_part, report: AssemblyReport) -> None:
    """List a cloned master in the presentation, as PowerPoint expects."""
    for rel in prs.part.rels.values():
        if not rel.is_external and rel.reltype == RT.SLIDE_MASTER \
                and rel.target_part is master_part:
            return
    rId = prs.part.relate_to(master_part, RT.SLIDE_MASTER)
    lst = prs._element.get_or_add_sldMasterIdLst()
    used = [int(e.get("id")) for e in lst if (e.get("id") or "").isdigit()]
    el = etree.SubElement(lst, qn("p:sldMasterId"))
    el.set("id", str(max(used) + 1 if used else 2147483649))
    el.set(qn("r:id"), rId)
    report.masters_added += 1


def _copy_background(src_slide, dst_slide) -> None:
    src_bg = src_slide._element.find("{%s}cSld/{%s}bg" % (P_NS, P_NS))
    if src_bg is None:
        return
    dst_cSld = dst_slide._element.find("{%s}cSld" % P_NS)
    for existing in dst_cSld.findall("{%s}bg" % P_NS):
        dst_cSld.remove(existing)
    dst_cSld.insert(0, copy.deepcopy(src_bg))


def copy_slide(src_slide, dst_prs, cloner: PartCloner, report: AssemblyReport):
    package = dst_prs.part.package

    layout_part = cloner.clone(src_slide.part.part_related_by(RT.SLIDE_LAYOUT))
    for rel in layout_part.rels.values():
        if not rel.is_external and rel.reltype == RT.SLIDE_MASTER:
            _register_master(dst_prs, rel.target_part, report)
            break

    slide_part = SlidePart.new(free_partname(package), package, layout_part)
    rId = dst_prs.part.relate_to(slide_part, RT.SLIDE)
    dst_prs.slides._sldIdLst.add_sldId(rId)
    dst_slide = slide_part.slide

    _copy_background(src_slide, dst_slide)

    dst_spTree = dst_slide.shapes._spTree
    for child in src_slide.shapes._spTree:
        if etree.QName(child).localname in ("nvGrpSpPr", "grpSpPr"):
            continue  # the destination keeps its own tree-level properties
        el = copy.deepcopy(child)
        report.rels_rewritten += remap_rids(el, src_slide.part, slide_part, cloner)
        dst_spTree.append(el)

    if src_slide.has_notes_slide:
        text = src_slide.notes_slide.notes_text_frame.text
        if text.strip():
            dst_slide.notes_slide.notes_text_frame.text = text

    report.slides += 1
    return dst_slide


def assemble(items, out_path, template=None, export_id="exp0001") -> AssemblyReport:
    """items: sequence of dicts with keys pptx / module_id / version_id.

    `template` supplies the deck-level settings (slide size, and the master that
    any future blank slide would use). Its own slides are dropped; page content
    always comes from `items`.
    """
    items = list(items)
    if not items:
        raise ValueError("nothing to assemble")

    base = Path(template) if template else Path(items[0]["pptx"])
    dst = Presentation(str(base))
    _strip_slides(dst)

    report = AssemblyReport()
    cloner = PartCloner(dst.part.package)

    for item in items:
        src = Presentation(str(item["pptx"]))
        if (src.slide_width, src.slide_height) != (dst.slide_width, dst.slide_height):
            report.size_mismatches.append(str(item["pptx"]))
        slide = copy_slide(src.slides[0], dst, cloner, report)
        marker.stamp(slide, item.get("module_id", "?"),
                     item.get("version_id", "?"), export_id)

    manifest.write(dst, {
        "export_id": export_id,
        "items": [{"position": i + 1,
                   "module_id": item.get("module_id", "?"),
                   "version_id": item.get("version_id", "?")}
                  for i, item in enumerate(items)],
    })

    report.parts_cloned = cloner.cloned_count
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    dst.save(str(out_path))
    return report
