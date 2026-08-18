"""Recognise a deck that came back from a client meeting.

For each returned page, answer two questions: where did it come from, and did it
change. Then, across the whole deck, answer a third: what did the presenter drop.

Identification runs three levels deep, exactly as the platform plan describes:

  marker      the off-canvas shape name — authoritative when present
  manifest    tells us what the export contained, so deletions are detectable
              even when a page never comes back to be inspected
  fingerprint the fallback when a marker was stripped: nearest neighbour by
              perceptual hash and text similarity, offered to a human rather
              than applied silently

Nothing here decides anything on its own. It produces a decision queue.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation

from . import manifest, marker
from .fingerprint import (IDENTICAL_MAX, SIMILAR_MAX, dhash, hamming,
                          text_hash, text_similarity)
from .render import deck_to_pngs
from .split import _harvest, SlideRecord

UNCHANGED = "unchanged"
MODIFIED = "modified"
NEW = "new"
UNMATCHED = "unmatched"
DELETED = "deleted"

# What a human is asked to do with each outcome.
SUGGESTED = {
    UNCHANGED: "忽略",
    MODIFIED: "存为该模块的新版本",
    NEW: "作为新模块入库，进打标流程",
    UNMATCHED: "人工确认来源（指纹给出候选）",
    DELETED: "记为被删信号，计入该模块留存率",
}


@dataclass
class SlideVerdict:
    position: int
    status: str
    module_id: str = ""
    version_id: str = ""
    match_method: str = ""
    text_similarity: float = 0.0
    visual_distance: int = 0
    candidates: list = field(default_factory=list)
    note: str = ""

    @property
    def suggestion(self) -> str:
        return SUGGESTED.get(self.status, "")


def _page_state(slide, png):
    rec = SlideRecord(index=0, pptx_path=Path("."), text="", notes="")
    _harvest(slide, rec)
    return rec.text, text_hash(rec.text), (dhash(png) if png else 0)


def analyse(returned_deck: Path, index: dict, work_dir: Path,
            dpi: int = 110) -> list[SlideVerdict]:
    returned_deck, work_dir = Path(returned_deck), Path(work_dir)
    pages_by_uid = {p["uid"]: p for p in index["pages"]}

    prs = Presentation(str(returned_deck))
    pngs = deck_to_pngs(returned_deck, work_dir, prefix="ret", dpi=dpi)

    verdicts: list[SlideVerdict] = []
    seen_versions: set[str] = set()

    for i, slide in enumerate(prs.slides, start=1):
        png = pngs[i - 1] if i - 1 < len(pngs) else None
        text, thash, vhash = _page_state(slide, png)
        info = marker.read(slide)

        if info and info["version_id"] in pages_by_uid:
            origin = pages_by_uid[info["version_id"]]
            seen_versions.add(info["version_id"])
            sim = text_similarity(text, origin["text"])
            dist = hamming(vhash, origin["dhash"]) if vhash and origin["dhash"] else 64
            unchanged = thash == origin["text_hash"] and dist <= IDENTICAL_MAX
            verdicts.append(SlideVerdict(
                position=i, status=UNCHANGED if unchanged else MODIFIED,
                module_id=info["module_id"], version_id=info["version_id"],
                match_method="marker", text_similarity=sim, visual_distance=dist))
            continue

        # No usable marker — fall back to fingerprint search over the library.
        # Visual similarity alone is not enough to propose a candidate: two
        # sparse pages are near-identical to a perceptual hash simply because
        # both are mostly white, which turns every newly written page into a
        # false match. Text has to agree as well.
        scored = []
        for uid, page in pages_by_uid.items():
            sim = text_similarity(text, page["text"])
            dist = hamming(vhash, page["dhash"]) if vhash and page["dhash"] else 64
            if sim >= 0.55 or (sim >= 0.3 and dist <= SIMILAR_MAX):
                scored.append((sim, -dist, uid, page))
        scored.sort(reverse=True)

        if not scored:
            verdicts.append(SlideVerdict(position=i, status=NEW,
                                         match_method="none",
                                         note="库中没有近似页"))
            continue

        sim, neg_dist, uid, page = scored[0]
        seen_versions.add(uid)
        verdicts.append(SlideVerdict(
            position=i, status=UNMATCHED, module_id=page["module_id"],
            version_id=uid, match_method="fingerprint", text_similarity=sim,
            visual_distance=-neg_dist,
            candidates=[c[2] for c in scored[:3]],
            note="标记丢失，按指纹给出候选"))

    export = manifest.read(prs)
    if export:
        for item in export.get("items", []):
            if item["version_id"] not in seen_versions:
                verdicts.append(SlideVerdict(
                    position=0, status=DELETED,
                    module_id=item.get("module_id", ""),
                    version_id=item["version_id"], match_method="manifest",
                    note="导出时第 %s 页，回传时已不在" % item.get("position", "?")))
    return verdicts
