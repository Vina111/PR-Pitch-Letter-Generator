"""Build the searchable catalogue: ingest -> tag -> group -> deduplicate.

Three things happen here that a flat page list cannot express.

**Grouping.** A case is not always one page. Section dividers ("01 产品传播案例")
open a run, a page with a real headline opens a case, and bare continuation pages
("策略STRATEGY", "成果RESULT") belong to the case above them. Grouping proposes
those boundaries so a reviewer confirms runs rather than re-reading every page.

**Deduplication.** The same case appears in several decks — the AUTEL CES page
sits in two of them, the LONGi Davos page in two more. Those collapse into one
module carrying several versions, which is what makes "which version do I send"
a question the library can answer.

**Confidence.** Every tag is a proposal with a score, so review starts where the
evidence is thinnest instead of at page one.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import pdfdoc, tagger
from .fingerprint import dhash, hamming, text_hash, text_similarity

CONTINUATION = re.compile(
    r"^\s*(策略\s*STRATEGY|成果\s*RESULT|STRATEGY|RESULT|背景|挑战|方案|结果)\s*$")

# Text is the primary signal: these pages are prose-heavy, and the same case
# restated in another deck keeps its wording while the layout drifts (a headline
# wraps differently, a logo moves). Requiring visual agreement as well rejected
# real duplicates at 0.94 text similarity, so a strong textual match stands on
# its own and the visual check only backs up the weaker band.
SAME_MODULE_TEXT_STRONG = 0.90
SAME_MODULE_TEXT_WEAK = 0.82
SAME_MODULE_VISUAL = 12


def _doc_year_hint(title: str, pages: list) -> str:
    years = tagger.YEAR.findall(title or "")
    if years:
        return years[-1]
    for page in pages[:3]:
        found = tagger.YEAR.findall(page.text)
        if found:
            return found[-1]
    return ""


def _starts_new_module(page_tags, title: str, prev_type: str) -> bool:
    if page_tags.page_type in ("封面", "封底", "目录", "过渡页"):
        return True
    if prev_type in ("封面", "封底", "目录", "过渡页"):
        return True
    if CONTINUATION.match((title or "").strip()):
        return False          # attaches to the case above
    if not (title or "").strip():
        return False          # untitled page continues its predecessor
    return True


def build(sources, out_dir: Path, thumb_width: int = 480, log=print) -> dict:
    out_dir = Path(out_dir)
    archive = out_dir / "archive"
    archive.mkdir(parents=True, exist_ok=True)

    started = time.time()
    docs, pages = [], []

    for n, src in enumerate(sources):
        src = Path(src)
        doc_id = chr(ord("A") + n) if n < 26 else "D%d" % n
        kept = archive / ("%s.pdf" % doc_id)
        if kept.resolve() != src.resolve():
            shutil.copyfile(src, kept)

        title = pdfdoc.doc_title(kept) or src.stem
        records = pdfdoc.split(kept, out_dir / doc_id, thumb_width=thumb_width)
        year_hint = _doc_year_hint(title, records)
        log("  %s  %-40s %3d pages" % (doc_id, title[:40], len(records)))

        docs.append({"id": doc_id, "title": title, "file": str(kept),
                     "orig_name": src.name, "pages": len(records),
                     "year_hint": year_hint})

        prev_type = ""
        section = ""
        for rec in records:
            tags = tagger.tag_page(
                rec.text, rec.title, rec.word_count, rec.image_count,
                is_first=(rec.index == 1), is_last=(rec.index == len(records)),
                doc_year_hint=year_hint)
            if tags.page_type == "过渡页" and rec.title:
                section = rec.title.strip()

            pages.append({
                "uid": "%s:%d" % (doc_id, rec.index),
                "doc": doc_id, "doc_title": title, "index": rec.index,
                "png": str(rec.png_path) if rec.png_path else "",
                "title": rec.title, "text": rec.text,
                "snippet": " ".join(rec.lines[1:6])[:220],
                "words": rec.word_count, "images": rec.image_count,
                "section": section,
                "tags": tags.as_dict(),
                "review": {"status": "pending",
                           "weak_fields": tagger.weakest_fields(tags)},
                "text_hash": text_hash(rec.text),
                "dhash": dhash(rec.png_path) if rec.png_path else 0,
                "starts_module": _starts_new_module(tags, rec.title, prev_type),
                "last_used": None, "use_count": 0,
            })
            prev_type = tags.page_type

    groups = _group(pages)
    modules = _dedupe(groups, pages)

    index = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "docs": docs, "pages": pages, "groups": groups, "modules": modules,
        "vocab": {
            "region": list(tagger.REGION), "industry": list(tagger.INDUSTRY),
            "service": list(tagger.SERVICE), "event": list(tagger.EVENT),
            "page_type": ["封面", "目录", "过渡页", "正文", "正文续页", "封底"],
        },
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    log("  built %d pages / %d groups / %d modules in %.1fs"
        % (len(pages), len(groups), len(modules), time.time() - started))
    return index


def _group(pages: list) -> list:
    """Consecutive pages within one document that form a single case."""
    groups, current = [], None
    by_uid = {p["uid"]: p for p in pages}

    for page in pages:
        new_doc = current is None or current["doc"] != page["doc"]
        if new_doc or page["starts_module"]:
            current = {"group_id": "g%03d" % (len(groups) + 1),
                       "doc": page["doc"], "section": page["section"],
                       "title": page["title"] or "(无标题)",
                       "members": [], "page_type": page["tags"]["page_type"]}
            groups.append(current)
        current["members"].append(page["uid"])

    for group in groups:
        first = by_uid[group["members"][0]]
        # A continuation page that names a different client than its head page
        # has probably been attached to the wrong case. Real example: a
        # "策略STRATEGY" page about one brand sitting directly after another
        # brand's case page. Flag it rather than guess.
        head_clients = set(first["tags"]["clients"])
        for uid in group["members"][1:]:
            tail_clients = set(by_uid[uid]["tags"]["clients"])
            if head_clients and tail_clients and not (head_clients & tail_clients):
                by_uid[uid]["review"]["status"] = "needs_check"
                by_uid[uid]["review"]["note"] = (
                    "续页客户(%s)与本组首页(%s)不一致，请确认归属"
                    % ("/".join(sorted(tail_clients)), "/".join(sorted(head_clients))))
        merged = {"regions": [], "industries": [], "services": [],
                  "events": [], "clients": [], "years": []}
        for uid in group["members"]:
            for key in merged:
                for value in by_uid[uid]["tags"].get(key, []):
                    if value not in merged[key]:
                        merged[key].append(value)
        group["tags"] = merged
        group["year"] = first["tags"]["year"]
        group["pages"] = len(group["members"])
    return groups


def _dedupe(groups: list, pages: list) -> list:
    """Collapse the same case appearing in more than one deck into one module."""
    by_uid = {p["uid"]: p for p in pages}
    parent = list(range(len(groups)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[max(a, b)] = min(a, b)

    def signature(group):
        # Anchor on the case's headline page, not the concatenation of the whole
        # run: the same case often carries a continuation page in one deck and
        # not in another, and concatenating drags the similarity below any
        # sensible threshold for what is plainly the same case.
        first = by_uid[group["members"][0]]
        return first["text"], first["dhash"], first["text_hash"]

    sigs = [signature(g) for g in groups]
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            if groups[i]["doc"] == groups[j]["doc"]:
                continue                      # versions live across decks here
            ti, di, hi = sigs[i]
            tj, dj, hj = sigs[j]
            if not ti.strip() or not tj.strip():
                continue                      # image-only pages: leave to review
            if hi == hj:
                union(i, j)
                continue
            similarity = text_similarity(ti, tj)
            if similarity >= SAME_MODULE_TEXT_STRONG:
                union(i, j)
                continue
            visual = hamming(di, dj) if di and dj else 64
            if similarity >= SAME_MODULE_TEXT_WEAK and visual <= SAME_MODULE_VISUAL:
                union(i, j)

    clustered: dict[int, list[int]] = {}
    for i in range(len(groups)):
        clustered.setdefault(find(i), []).append(i)

    modules = []
    for n, (_, members) in enumerate(sorted(clustered.items()), start=1):
        module_id = "m%03d" % n
        versions = []
        for i in members:
            groups[i]["module_id"] = module_id
            versions.append({"group_id": groups[i]["group_id"],
                             "doc": groups[i]["doc"],
                             "members": groups[i]["members"],
                             "pages": groups[i]["pages"]})
        head = groups[members[0]]
        modules.append({
            "module_id": module_id, "title": head["title"],
            "section": head["section"], "year": head["year"],
            "tags": head["tags"], "page_type": head["page_type"],
            "versions": versions, "version_count": len(versions),
            "default_version": versions[0]["group_id"],
        })
    return modules
