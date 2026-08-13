"""
Media Pitch Generator  (portable skill · LLM-agnostic · zero-dependency)
=========================================================================
Follows PR Desk's proven Pitch Drafter logic:

  INPUTS  : client + spokesperson name & title, what you're pitching (angle /
            news hook / why it's timely), OPTIONAL pasted background MATERIALS
            (press release, data, notes) — the "upload" step, and OPTIONAL
            target reporter + outlet for personalization.
  STRUCTURE: declarative headline-style subject -> greeting -> 3-4 short
            paragraphs: thesis (first sentence) -> why it matters -> source +
            credentials -> conversational ask.
  TONE    : conversational, confident, senior-PR-pro; never salesy, never a
            robot; respects the reporter's time.
  PERSONALIZATION: real or absent, never simulated — when a reporter is named,
            reference ONE specific recent piece of theirs WITH ITS DATE and
            offer a complementary angle; with no real coverage in hand, use a
            bracketed placeholder or omit personalization entirely.
  REGENERATE: a variant is a strategy change — the Nth angle lens from the SOP
            menu (ANGLE_MENU) — not a re-wording of the same thesis.

This module is intentionally FREE of any LLM call, HTTP server, or API key. It is
the OFFLINE half of a portable skill: it emits a deterministic structure skeleton
(with bracketed placeholders for the installing agent's LLM to fill) and validates
a draft against PR Desk's hard rules. The prose itself is written by whatever
LLM-powered agent installed the skill (Codex, Claude Code, WorkBuddy, ...).

Usage (CLI):
    python3 pitch.py --topic "..." --client Acme --spokesperson "Jane Doe" \
        --title "VP Ops" --outlet Wired --reporter "John Smith" \
        --material-text "Q2: 47% faster restocking" --variant 0
    python3 pitch.py --validate "$(cat my_pitch.txt)"   # rule check only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List


# --------------------------------------------------------------------------- #
#  PR Desk methodology — load this into your own prompt when generating.        #
# --------------------------------------------------------------------------- #
PRDESK_SPEC = """\
You are a senior PR account lead with a decade of experience writing journalist \
pitches. Write a cold pitch email.

VOICE: conversational, confident, concise. It must sound like a real senior \
practitioner wrote it — never a robot, never salesy, never corporate fluff. \
Respect the reporter's time and get to the point immediately.

STRUCTURE (follow exactly):
1. Subject line: a DECLARATIVE statement that reads like a headline (never a question).
2. A short greeting (use the reporter's first name when known).
3. Three to four short paragraphs:
   - Paragraph 1: the thesis / clear news hook in the FIRST sentence.
   - Paragraph 2: why it matters — NAME who in the outlet's readership is \
affected and how. Generic timeliness prose ("in a fast-moving market") is a \
failure; relevance means impact on the audience's community.
   - Paragraph 3: introduce the source — client + spokesperson + their credible \
title — and what they can offer a reporter.
   - Paragraph 4 (optional): a conversational, low-friction ask (e.g. a short \
briefing or a bylined idea).
4. Personalization is REAL OR ABSENT — never simulated. If a TARGET REPORTER is \
given and you have their recent coverage, reference ONE specific recent piece \
of theirs WITH ITS DATE and offer a COMPLEMENTARY angle that extends their \
storyline (not generic "I saw your article" filler). If you lack real coverage, \
insert a bracketed placeholder rather than inventing a title/URL/date. If no \
genuinely complementary connection exists, omit personalization entirely — an \
accurate on-beat pitch with no flattery beats counterfeit familiarity.

HARD RULES: under 150 words; subject at most ~9 words; NO bullet points; NO \
mention of attachments; NO inline hyperlinks in the body; NO flattery openers \
("I loved your article", "big fan", "I came across your piece", "I hope this \
finds you well"); NO AI-tell vocabulary ("excited to share", "revolutionary", \
"game-changing", "cutting-edge", "delve", "seamlessly", "in today's fast-paced \
world").
Base every claim on the client context and the pasted MATERIALS. Never invent \
facts, stats, or quotes not present in the inputs.\
"""

# SOP angle menu — a regenerate/variant is a *different angle from this menu*
# (a strategy change), never a re-wording of the same thesis.
ANGLE_MENU = [
    "product launch / new availability",
    "industry or consumer pain point",
    "use-case / scenario",
    "technical or clinical differentiation",
    "market-trend complement",
    "sample / review invitation",
    "expert or executive interview",
]


# --------------------------------------------------------------------------- #
#  I/O CONTRACT  — stable interface. Bump when changing fields.                 #
# --------------------------------------------------------------------------- #
@dataclass
class PitchInput:
    topic: str                         # what you're pitching: angle / hook / why timely (required)
    client: str = ""                  # client / company name
    spokesperson: str = ""            # spokesperson name
    spokesperson_title: str = ""      # spokesperson title (e.g. "CEO")
    outlet: str = ""                  # target publication
    reporter: str = ""                # target journalist (enables personalization)
    materials: List[str] = field(default_factory=list)  # pasted background material(s)
    message: str = ""                 # optional extra takeaway (folded into materials)
    tone: str = "professional"        # professional | conversational | bold
    max_words: int = 150              # hard cap
    variant: int = 0                  # 0 = default angle; >0 = regenerate a different angle


@dataclass
class PitchOutput:
    angle: str
    subject: str
    body: str
    word_count: int
    backend: str = "skeleton"         # this module only ever produces a skeleton
    validation_issues: List[str] = field(default_factory=list)
    referenced_coverage: List[str] = field(default_factory=list)  # for the agent to fill
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
#  Offline scaffold — deterministic, structurally faithful.                     #
# --------------------------------------------------------------------------- #
def build_skeleton(inp: PitchInput) -> PitchOutput:
    client = inp.client or "our client"
    sp = inp.spokesperson or "[Spokesperson]"
    title = f", {inp.spokesperson_title}" if inp.spokesperson_title else ""
    hook = inp.topic.strip().rstrip(". ")
    subject = f"{_cap(client)} {_hook_phrase(hook)}"
    greeting = f"Hi {inp.reporter.split()[0] if inp.reporter else '[First name]'},\n\n"

    mat_note = ""
    if inp.materials:
        mat_note = ("  [Weave in the provided background material — e.g. "
                    + _truncate(inp.materials[0], 140) + "]")

    p1 = (f"{_cap(sp)}{title} at {client} says the story on {hook} is about to "
          f"shift — and they've got the data to show it.{mat_note}")
    p2 = (f"It matters now because [why-it-matters: timeliness / the 'so what' "
          f"for {inp.outlet or 'readers'}]."
          + (f"  [{_truncate(inp.materials[0], 140)}]" if inp.materials else ""))
    p3 = (f"{_cap(sp)}{title} is available as a source: they can walk through "
          f"what's changing and what it means for the people affected.")
    p4 = (f"If it's useful, I can set up a 15-minute briefing or draft a bylined "
          f"explainer for {inp.outlet or 'your'} readers.")
    rep_line = ""
    if inp.reporter:
        rep_line = (
            f"\nGiven your recent coverage, I thought this complementary angle on "
            f"{hook} would land — [reference ONE specific recent piece and offer a "
            f"complementary angle]."
        )
    lens = ANGLE_MENU[(inp.variant - 1) % len(ANGLE_MENU)] if inp.variant > 0 else ""
    variant_tag = f"  [variant {inp.variant} — angle lens: {lens}]" if lens else ""
    body = (
        f"Subject: {subject}\n\n"
        + greeting
        + "\n\n".join([p1, p2, p3, p4, rep_line]).strip()
        + "\n\nBest,\n[Your name]"
        + variant_tag
    )

    issues = validate_pitch(body, inp.max_words)
    notes = ("Deterministic scaffold (PR Desk structure). The installing agent's "
             "LLM rewrites the prose and fills the [bracketed] placeholders.")
    if inp.materials:
        notes += " Materials detected — use them as the fact base."
    else:
        notes += " No materials — ask the user to paste background material."
    if lens:
        notes += (f" Variant lens = '{lens}': rebuild P1/P2 around this angle "
                  "(ask the user for the input it needs) — a variant is a "
                  "strategy change, not a re-wording.")
    return PitchOutput(
        angle=hook if not lens else f"{hook} (lens: {lens})",
        subject=subject, body=body,
        word_count=len(re.findall(r"\S+", body)),
        backend="skeleton", validation_issues=issues, note=notes,
    )


# The offline default. The "live" generation is done by the agent's own LLM.
def generate_pitch(inp: PitchInput) -> PitchOutput:
    return build_skeleton(inp)


# --------------------------------------------------------------------------- #
#  Validator — checks a draft against PR Desk's hard rules plus the            #
#  journalist-facing spam signals (flattery openers, AI-tell vocabulary,       #
#  undated coverage references, overlong subjects).                            #
# --------------------------------------------------------------------------- #
_FLATTERY_OPENERS = [
    r"\bi hope this (?:email |message )?finds you well\b",
    r"\bi(?:'m| am) a big fan\b",
    r"\bbig fan of your\b",
    r"\bi (?:loved|really enjoyed|enjoyed) your (?:article|piece|story|work)\b",
    r"\bi (?:came|stumbled) across your (?:article|piece|profile|work)\b",
    r"\bi(?:'ve| have) been following your (?:work|coverage|writing)\b",
]
_AI_TELLS = [
    r"\bexcited to (?:share|announce)\b",
    r"\brevolutionary\b|\brevolutioni[sz]e\w*\b",
    r"\bgame[- ]chang\w+\b",
    r"\bcutting[- ]edge\b",
    r"\bdelv(?:e|es|ed|ing)\b",
    r"\bseamless(?:ly)?\b",
    r"\bin today'?s fast[- ]paced world\b",
]
# A coverage reference must carry a date (or a [bracketed] placeholder) so a
# fabricated "your recent piece" can never pass silently.
_COVERAGE_REF = re.compile(
    r"\byour (?:recent |latest )?(?:piece|article|story|coverage|reporting|"
    r"feature|interview)\b", re.I)
_DATE_TOKEN = re.compile(
    r"\b(?:jan(?:\.|uary)?|feb(?:\.|ruary)?|march|apr(?:\.|il)?|may\s+\d|june|"
    r"july|aug(?:\.|ust)?|sept?(?:\.|ember)?|oct(?:\.|ober)?|nov(?:\.|ember)?|"
    r"dec(?:\.|ember)?|20\d\d|last\s+(?:week|month|year)|this\s+(?:week|month)|"
    r"yesterday|earlier\s+this)\b", re.I)


def validate_pitch(text: str, max_words: int = 150) -> List[str]:
    issues: List[str] = []
    if not text or not text.strip():
        return ["empty draft"]

    words = len(re.findall(r"\S+", text))
    if words >= max_words:
        issues.append(f"word count {words} >= {max_words} (must be under {max_words})")

    if re.search(r"https?://", text):
        issues.append("contains inline hyperlink (remove body links)")

    if re.search(r"(^|\n)\s*[-*•·‣–—]\s+\S", text):
        issues.append("contains bullet points (use prose paragraphs)")

    if re.search(r"\b(attached|attachment|enclosed)\b", text, re.I):
        issues.append("mentions an attachment (remove it)")

    for pat in _FLATTERY_OPENERS:
        m = re.search(pat, text, re.I)
        if m:
            issues.append(f'flattery opener "{m.group(0)}" (praise without '
                          "substance reads as unread — cut it)")

    for pat in _AI_TELLS:
        m = re.search(pat, text, re.I)
        if m:
            issues.append(f'AI-tell phrase "{m.group(0)}" (rewrite in plain '
                          "language — this vocabulary flags a machine draft)")

    for line in text.splitlines():
        if _COVERAGE_REF.search(line) and "[" not in line \
                and not _DATE_TOKEN.search(line):
            issues.append("coverage reference lacks a date (cite the piece's "
                          "date, use a [bracketed placeholder], or omit "
                          "personalization — never simulate familiarity)")
            break

    subject_line = _detect_subject(text)
    if subject_line:
        s = subject_line.strip().rstrip()
        if s.endswith("?"):
            issues.append("subject is a question (make it a declarative headline)")
        if re.match(r"^(what|why|how|when|where|who|is|are|can|do|does|did|will|"
                    r"should|could|would|has|have|which)\b", s, re.I):
            issues.append("subject looks like a question (make it declarative)")
        s_words = len(s.split())
        if s_words > 9 or len(s) > 60:
            issues.append(f"subject is {s_words} words / {len(s)} chars "
                          "(keep it within ~9 words / 60 chars so it survives "
                          "a mobile inbox)")
    else:
        issues.append("no subject line found (add a declarative headline subject)")

    return issues


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _hook_phrase(hook: str) -> str:
    return f"just changed the conversation on {hook}"


def _truncate(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] + ("…" if len(s) > n else "")


def _detect_subject(text: str) -> str:
    for ln in text.splitlines():
        s = ln.strip()
        if s.lower().startswith("subject:"):
            return s.split(":", 1)[1]
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    # Treat a short leading line as the subject.
    if first and len(first.split()) <= 18 and not first.endswith((".", ",")):
        return first
    return ""


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #
def _main() -> None:
    p = argparse.ArgumentParser(
        description="Media Pitch Generator — PR Desk-faithful, LLM-agnostic scaffold/validator")
    p.add_argument("--topic", help="what you're pitching: angle / hook / why timely")
    p.add_argument("--client", default="")
    p.add_argument("--spokesperson", default="")
    p.add_argument("--title", dest="spokesperson_title", default="")
    p.add_argument("--outlet", default="")
    p.add_argument("--reporter", default="")
    p.add_argument("--message", default="", help="extra takeaway (folded into materials)")
    p.add_argument("--material", action="append", default=[], metavar="PATH",
                   help="background material file (repeatable)")
    p.add_argument("--material-text", action="append", default=[], metavar="TEXT",
                   help="pasted background material (repeatable)")
    p.add_argument("--tone", default="professional")
    p.add_argument("--max-words", type=int, default=150)
    p.add_argument("--variant", type=int, default=0,
                   help=">0 = the Nth SOP angle lens (a strategy change, "
                        "not a re-wording)")
    p.add_argument("--validate", metavar="TEXT", help="validate a draft against PR Desk rules")
    p.add_argument("--json", action="store_true", help="emit raw JSON")
    args = p.parse_args()

    # --- validate mode ----------------------------------------------------- #
    if args.validate is not None:
        issues = validate_pitch(args.validate, args.max_words)
        if args.json:
            print(json.dumps({"valid": not issues, "issues": issues},
                             ensure_ascii=False, indent=2))
        else:
            if issues:
                print("ISSUES FOUND:")
                for i in issues:
                    print(f"  • {i}")
            else:
                print("OK — draft passes PR Desk hard rules.")
        return

    if not args.topic:
        p.error("--topic is required (or use --validate TEXT)")

    mats: List[str] = list(args.material_text)
    for path in args.material:
        try:
            mats.append(Path(path).read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            print(f"[warn] cannot read {path}: {e}", file=sys.stderr)
    if args.message:
        mats.append(args.message)

    inp = PitchInput(
        topic=args.topic, client=args.client, spokesperson=args.spokesperson,
        spokesperson_title=args.spokesperson_title, outlet=args.outlet,
        reporter=args.reporter, materials=mats, tone=args.tone,
        max_words=args.max_words, variant=args.variant,
    )
    out = generate_pitch(inp)
    if args.json:
        print(json.dumps(out.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"[backend: {out.backend}]")
        if out.note:
            print(f"({out.note})\n")
        print(f"ANGLE   : {out.angle}")
        print(f"SUBJECT : {out.subject}")
        print(f"WORDS   : {out.word_count}")
        if out.validation_issues:
            print("SKELETON CHECK:")
            for i in out.validation_issues:
                print(f"  • {i}")
        print("-" * 60)
        print(out.body)


if __name__ == "__main__":
    _main()
