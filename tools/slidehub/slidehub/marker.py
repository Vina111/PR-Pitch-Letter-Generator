"""Embed and recover a slide's origin id.

The id rides in the *shape name* of an empty shape parked far off the canvas.
Shape names survive the edits that matter — reordering slides, copy/paste between
decks, editing text, swapping images, Save As — and they are invisible everywhere
a presenter looks: not on the canvas, not in the outline, not in the printout.
"""
from __future__ import annotations

from pptx.util import Emu

PREFIX = "SLIDEHUB"
# Field separator inside the marker. Not ":" — identifiers routinely contain
# one (a page uid like "A:1" would be split into two fields and the lookup would
# miss every page), and a silent identification failure is the worst possible
# outcome here. Ids must never contain this character; `stamp` enforces it.
SEP = "|"
OFFSCREEN = Emu(-10_000_000)
TINY = Emu(1)


def stamp(slide, module_id: str, version_id: str, export_id: str) -> str:
    for name, value in (("module_id", module_id), ("version_id", version_id),
                        ("export_id", export_id)):
        if SEP in str(value):
            raise ValueError("%s must not contain %r: %r" % (name, SEP, value))
    payload = SEP.join((PREFIX, str(module_id), str(version_id), str(export_id)))
    box = slide.shapes.add_textbox(OFFSCREEN, OFFSCREEN, TINY, TINY)
    box.name = payload
    return payload


def read(slide) -> dict | None:
    for shape in slide.shapes:
        name = shape.name or ""
        if not name.startswith(PREFIX + SEP):
            continue
        parts = name.split(SEP)
        if len(parts) != 4:
            continue
        return {"module_id": parts[1], "version_id": parts[2], "export_id": parts[3]}
    return None
