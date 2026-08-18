"""The page index: ingest decks into it, cluster duplicates, read pages back.

Deliberately a JSON file rather than a database. The spike's job is to answer a
fidelity question, and a file that can be opened and eyeballed is worth more here
than schema migrations. The field names are chosen to survive the move to
Postgres unchanged.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .fingerprint import (IDENTICAL_MAX, SIMILAR_MAX, dhash, hamming,
                          struct_hash, text_hash, text_similarity)
from .render import deck_to_pngs
from .split import split_deck


@dataclass
class Page:
    uid: str
    deck_id: str
    deck_name: str
    index: int
    pptx: str
    png: str
    title: str
    text: str
    notes: str
    text_hash: str
    dhash: int
    struct_hash: str
    media_sha: list[str] = field(default_factory=list)
    layout: str = ""
    flags: dict = field(default_factory=dict)
    module_id: str = ""


def _title_of(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:60]
    return "(无文字)"


def ingest(deck_paths, out_dir: Path, dpi: int = 110, log=print) -> dict:
    out_dir = Path(out_dir)
    pages_dir = out_dir / "pages"
    thumbs_dir = out_dir / "thumbs"
    for d in (pages_dir, thumbs_dir):
        d.mkdir(parents=True, exist_ok=True)

    decks, pages = [], []
    for n, deck_path in enumerate(deck_paths):
        deck_path = Path(deck_path)
        deck_id = chr(ord("A") + n) if n < 26 else "D%d" % n
        log("  ingesting %s ..." % deck_path.name)

        slide_dir = pages_dir / deck_id
        records = split_deck(deck_path, slide_dir)
        thumbs = deck_to_pngs(deck_path, thumbs_dir / deck_id, prefix=deck_id, dpi=dpi)

        if len(thumbs) != len(records):
            log("    ! renderer produced %d images for %d slides"
                % (len(thumbs), len(records)))

        for rec in records:
            png = thumbs[rec.index - 1] if rec.index - 1 < len(thumbs) else None
            pages.append(Page(
                uid="%s:%d" % (deck_id, rec.index),
                deck_id=deck_id, deck_name=deck_path.name, index=rec.index,
                pptx=str(rec.pptx_path), png=str(png) if png else "",
                title=_title_of(rec.text), text=rec.text, notes=rec.notes,
                text_hash=text_hash(rec.text),
                dhash=dhash(png) if png else 0,
                struct_hash=struct_hash(rec.geometry),
                media_sha=rec.media_sha, layout=rec.layout_name,
                flags={"chart": rec.has_chart, "table": rec.has_table,
                       "group": rec.has_group, "smartart": rec.has_smartart,
                       "shapes": len(rec.shape_kinds)},
            ))
        decks.append({"id": deck_id, "name": deck_path.name,
                      "path": str(deck_path), "slides": len(records)})

    modules = cluster(pages)
    index = {"decks": decks, "pages": [asdict(p) for p in pages], "modules": modules}
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def cluster(pages: list[Page]) -> list[dict]:
    """Union-find over pairwise similarity.

    A pair is the same module when the rendering is near-identical, or when the
    words match closely *and* the rendering is at least in the neighbourhood —
    the conjunction is what stops two different case studies built on one layout
    from collapsing into each other.
    """
    parent = list(range(len(pages)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            a, b = pages[i], pages[j]
            visual = hamming(a.dhash, b.dhash) if (a.dhash and b.dhash) else 64
            if a.text_hash == b.text_hash and a.text.strip():
                union(i, j)
            elif visual <= IDENTICAL_MAX:
                union(i, j)
            elif visual <= SIMILAR_MAX and text_similarity(a.text, b.text) >= 0.85:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(pages)):
        groups.setdefault(find(i), []).append(i)

    modules = []
    for n, (_, members) in enumerate(sorted(groups.items()), start=1):
        module_id = "m%03d" % n
        for i in members:
            pages[i].module_id = module_id
        modules.append({
            "module_id": module_id,
            "title": pages[members[0]].title,
            "members": [pages[i].uid for i in members],
            "version_count": len(members),
        })
    return modules


def load(out_dir: Path) -> dict:
    return json.loads((Path(out_dir) / "index.json").read_text(encoding="utf-8"))


def page_map(index: dict) -> dict:
    return {p["uid"]: p for p in index["pages"]}
