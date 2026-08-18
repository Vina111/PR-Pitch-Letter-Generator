"""The deck-level export manifest.

The per-page marker says where one page came from. The manifest says what the
whole export contained — which is the only way to notice a page that came back
*missing*, and the only way to recover if the markers get stripped.

It lives in a custom XML part, the standard OPC slot for application data.
PowerPoint carries these parts through edit-and-save untouched, and they are
invisible in the UI.
"""
from __future__ import annotations

import json

from pptx.opc.package import Part
from pptx.opc.packuri import PackURI

RELTYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml"
CONTENT_TYPE = "application/xml"
PARTNAME = "/customXml/slidehub.xml"
ROOT_OPEN = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<slidehub><![CDATA['
ROOT_CLOSE = "]]></slidehub>"


def write(prs, payload: dict) -> None:
    blob = (ROOT_OPEN + json.dumps(payload, ensure_ascii=False) + ROOT_CLOSE).encode("utf-8")
    package = prs.part.package
    for rel in list(prs.part.rels.values()):
        if not rel.is_external and rel.reltype == RELTYPE \
                and str(rel.target_part.partname) == PARTNAME:
            rel.target_part._blob = blob
            return
    part = Part(PackURI(PARTNAME), CONTENT_TYPE, package, blob)
    prs.part.relate_to(part, RELTYPE)


def read(prs) -> dict | None:
    for rel in prs.part.rels.values():
        if rel.is_external or rel.reltype != RELTYPE:
            continue
        try:
            text = rel.target_part.blob.decode("utf-8")
        except (AttributeError, UnicodeDecodeError):
            continue
        start, end = text.find("<![CDATA["), text.rfind("]]>")
        if start == -1 or end == -1:
            continue
        try:
            return json.loads(text[start + 9:end])
        except json.JSONDecodeError:
            continue
    return None
