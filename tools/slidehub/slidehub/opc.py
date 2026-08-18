"""Low-level OPC surgery: deep-cloning parts between packages and remapping
relationship ids inside XML that gets moved across package boundaries.

This is the layer everything else in the spike stands on. Two distinct jobs:

1. `PartCloner.clone` copies a part (and everything it transitively references)
   from one package into another **while preserving each part's internal rIds**.
   Preserving them matters: a chart part's own XML refers to its colors/style
   parts by rId, so re-allocating ids would silently break the chart. Because
   the clone keeps the same ids, the copied blob stays valid untouched.

2. `remap_rids` handles the other case — XML grafted into a part that already
   exists in the destination (a slide's shape tree). There the source rIds may
   collide with ids the destination part already uses, so fresh ids are minted
   and every r:-namespaced attribute in the grafted subtree is rewritten.
"""
from __future__ import annotations

import re

from pptx.opc.constants import RELATIONSHIP_TARGET_MODE as RTM
from pptx.opc.package import Part, _Relationship
from pptx.opc.packuri import PackURI

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _partname_tmpl(partname) -> str:
    """'/ppt/media/image12.png' -> '/ppt/media/image%d.png' for next_partname."""
    s = str(partname)
    m = re.match(r"^(.*?)(\d+)(\.[^.]+)$", s)
    if m:
        return "%s%%d%s" % (m.group(1), m.group(3))
    head, _, ext = s.rpartition(".")
    return "%s%%d.%s" % (head, ext) if head else s + "%d"


class PartCloner:
    """Clones parts into `dst_package`, memoised so a part shared by several
    slides is copied once and a layout<->master reference cycle terminates."""

    def __init__(self, dst_package):
        self.pkg = dst_package
        self._cache: dict[int, Part] = {}
        self.cloned_count = 0
        # Package.next_partname only sees parts already reachable from the
        # package root, and a clone is not reachable until something relates to
        # it — which happens after its children are cloned. Allocating names
        # against the package alone therefore hands out the same name twice.
        # Names are tracked here instead, starting from what is already in use.
        self._taken: set[str] = {str(p.partname) for p in dst_package.iter_parts()}

    def _next_partname(self, src_partname) -> PackURI:
        tmpl = _partname_tmpl(src_partname)
        n = 1
        while True:
            candidate = tmpl % n
            if candidate not in self._taken:
                self._taken.add(candidate)
                return PackURI(candidate)
            n += 1

    def clone(self, src_part) -> Part:
        key = id(src_part)
        if key in self._cache:
            return self._cache[key]

        new_part = Part(
            self._next_partname(src_part.partname),
            src_part.content_type,
            self.pkg,
            src_part.blob,
        )
        # Cache before recursing: layout -> master -> layout is a real cycle.
        self._cache[key] = new_part
        self.cloned_count += 1

        for rel in src_part.rels.values():
            if rel.is_external:
                _add_rel_with_id(new_part, rel.rId, rel.reltype, rel.target_ref, True)
            else:
                _add_rel_with_id(
                    new_part, rel.rId, rel.reltype, self.clone(rel.target_part), False
                )
        return new_part


def _add_rel_with_id(part, rId, reltype, target, is_external):
    """Attach a relationship under a caller-chosen rId.

    python-pptx only exposes id-allocating helpers; the spike needs id-preserving
    ones, so the relationship is constructed and inserted directly.
    """
    part.rels._rels[rId] = _Relationship(
        part.partname.baseURI,
        rId,
        reltype,
        RTM.EXTERNAL if is_external else RTM.INTERNAL,
        target,
    )
    return rId


def remap_rids(element, src_part, dst_part, cloner):
    """Rewrite every r:-namespaced attribute in `element` so it resolves against
    `dst_part`, cloning the referenced parts as needed.

    Covers a:blip/@r:embed, a:hlinkClick/@r:id, c:chart/@r:id, p:oleObj/@r:id,
    p14:media/@r:link, svgBlip/@r:embed and anything else in the same namespace,
    because it matches on namespace rather than an allow-list of tags.

    Returns the number of references rewritten.
    """
    rewritten = 0
    src_rels = src_part.rels
    seen: dict[str, str] = {}

    for el in element.iter():
        for name, value in list(el.attrib.items()):
            if not name.startswith("{%s}" % R_NS):
                continue
            old_rId = value
            if old_rId in seen:
                el.set(name, seen[old_rId])
                rewritten += 1
                continue
            rel = src_rels.get(old_rId)
            if rel is None:
                # Dangling reference in the source file; drop the attribute so the
                # destination does not carry a broken pointer.
                del el.attrib[name]
                continue
            if rel.is_external:
                new_rId = dst_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
            else:
                new_rId = dst_part.relate_to(cloner.clone(rel.target_part), rel.reltype)
            seen[old_rId] = new_rId
            el.set(name, new_rId)
            rewritten += 1
    return rewritten
