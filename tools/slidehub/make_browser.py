"""Emit the library browser: a single self-contained HTML page.

Everything the page needs is inlined — index and thumbnails alike — so it opens
from a file, from a shared link, or from a laptop with no network, and keeps
working. It is the review surface (requirement 2) and the search surface
(requirement 3), and it ends by handing over the exact `compose` command for the
pages picked (requirement 4).
"""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent


def thumbnails(index: dict, width: int = 320, quality: int = 68) -> dict:
    out = {}
    for page in index["pages"]:
        if not page.get("png"):
            continue
        with Image.open(page["png"]) as im:
            im = im.convert("RGB")
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=quality, optimize=True)
        out[page["uid"]] = base64.b64encode(buf.getvalue()).decode()
    return out


def payload(index: dict) -> dict:
    """Trim the index to what the page actually renders or searches."""
    group_of = {}
    for group in index["groups"]:
        for uid in group["members"]:
            group_of[uid] = group

    pages = []
    for page in index["pages"]:
        group = group_of.get(page["uid"], {})
        tags = page["tags"]
        pages.append({
            "uid": page["uid"], "doc": page["doc"], "docTitle": page["doc_title"],
            "index": page["index"], "title": page["title"] or "(无标题)",
            "snippet": page["snippet"], "text": page["text"][:1400],
            "section": page["section"],
            "year": tags["year"], "regions": tags["regions"],
            "industries": tags["industries"], "services": tags["services"],
            "events": tags["events"], "clients": tags["clients"],
            "pageType": tags["page_type"],
            "conf": tags["confidence"],
            "weak": page["review"]["weak_fields"],
            "status": page["review"]["status"],
            "note": page["review"].get("note", ""),
            "group": group.get("group_id", ""),
            "module": group.get("module_id", ""),
            "groupPages": group.get("pages", 1),
            "lastUsed": page.get("last_used"),
            "useCount": page.get("use_count", 0),
        })

    modules = [{
        "id": m["module_id"], "title": m["title"], "versions": m["version_count"],
        "members": [u for v in m["versions"] for u in v["members"]],
    } for m in index["modules"]]

    return {
        "builtAt": index["built_at"],
        "docs": [{"id": d["id"], "title": d["title"], "pages": d["pages"],
                  "origName": d["orig_name"]} for d in index["docs"]],
        "pages": pages,
        "modules": modules,
        "vocab": index["vocab"],
    }


TEMPLATE = (HERE / "browser_template.html").read_text(encoding="utf-8")


def build(library: Path, out_html: Path, width: int = 320) -> Path:
    index = json.loads((Path(library) / "index.json").read_text(encoding="utf-8"))
    data = payload(index)
    data["thumbs"] = thumbnails(index, width=width)
    # The payload rides inside a <script type="application/json"> block, so any
    # literal "</script" in page text would close it early and break the page.
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/null", blob)
    out_html = Path(out_html)
    out_html.write_text(html, encoding="utf-8")
    return out_html


if __name__ == "__main__":
    lib = Path(sys.argv[1] if len(sys.argv) > 1 else "build/lib")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/library.html")
    written = build(lib, out)
    print("%s  (%.1f MB)" % (written, written.stat().st_size / 1e6))
