"""Page fingerprints — the basis for both deduplication and fidelity checking.

Four independent signals, because no single one is sufficient:

  text        catches "same words, redrawn" (a page rebuilt in a new template)
  perceptual  catches "same picture, retyped" (a screenshot-like duplicate) and
              is the one that answers "did assembly change how this looks?"
  structure   catches layout identity when both text and imagery differ slightly
  media       exact image reuse, and the cheap blocking key for large libraries
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from PIL import Image

_PUNCT = re.compile(r"[\s　·。，、；：？！“”‘’（）《》〈〉【】…—\-_/\\|,.;:?!\"'()\[\]{}<>]+")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return _PUNCT.sub("", text)


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def text_similarity(a: str, b: str) -> float:
    """Character-bigram Dice coefficient — works on Chinese, where whitespace
    tokenisation would collapse a whole sentence into one token."""
    na, nb = normalize_text(a), normalize_text(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    if len(na) < 2 or len(nb) < 2:
        return 1.0 if na == nb else 0.0
    ga = [na[i:i + 2] for i in range(len(na) - 1)]
    gb = [nb[i:i + 2] for i in range(len(nb) - 1)]
    sa, sb = {}, {}
    for g in ga:
        sa[g] = sa.get(g, 0) + 1
    for g in gb:
        sb[g] = sb.get(g, 0) + 1
    overlap = sum(min(c, sb.get(g, 0)) for g, c in sa.items())
    return 2.0 * overlap / (len(ga) + len(gb))


def dhash(image_path, size: int = 8) -> int:
    """Difference hash: 64 bits describing where the image gets lighter/darker.

    Robust to rescaling and mild compression, sensitive to layout and content
    shifts — the right trade for "does this page still look the same".
    """
    with Image.open(image_path) as im:
        im = im.convert("L").resize((size + 1, size), Image.LANCZOS)
        px = list(im.getdata())
    bits = 0
    for row in range(size):
        base = row * (size + 1)
        for col in range(size):
            bits = (bits << 1) | int(px[base + col] > px[base + col + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def color_signature(image_path, size: int = 8) -> list[int]:
    """Mean RGB on a size x size grid.

    dhash deliberately throws colour away, which makes it blind to the single
    most brand-damaging failure mode: a chart or accent bar repainting itself in
    another deck's palette. This keeps colour, coarsely enough to ignore
    antialiasing and JPEG noise.
    """
    with Image.open(image_path) as im:
        im = im.convert("RGB").resize((size, size), Image.LANCZOS)
        return [v for px in im.getdata() for v in px]


def color_distance(a: list[int], b: list[int]) -> float:
    """Mean absolute channel difference, 0-255. Roughly: 'how many shades off'."""
    if not a or not b or len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def struct_hash(geometry) -> str:
    payload = "|".join(",".join(str(v) for v in g) for g in sorted(map(tuple, geometry)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Thresholds, on a 64-bit hash. Calibrate against a real library before trusting
# them in production; these are the spike's starting points.
IDENTICAL_MAX = 2    # visually the same page
SIMILAR_MAX = 10     # same page, edited
FIDELITY_WARN = 8    # assembly likely changed the rendering (structure)
COLOR_WARN = 6.0     # assembly likely changed the palette (mean channel delta)
