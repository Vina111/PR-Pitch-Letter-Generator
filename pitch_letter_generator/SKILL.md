---
name: media-pitch-generator
description: >
  Generate cold journalist / PR media pitches and pitch strategy using PR Desk's
  Pitch Drafter logic plus a product/media-list SOP. Use when the user wants to
  draft, revise, validate, or batch-generate a press pitch, journalist outreach
  email, media pitch, product-launch pitch, interview pitch, review pitch, media
  list strategy, or outreach angle. When explicitly invoked, always asks the
  user a structured question sequence before generating a pitch letter, helping
  them decide product positioning, audience, spokesperson, facts, reporter fit,
  desired CTA, and outreach round. Mirrors the
  proven structure (declarative headline subject -> greeting -> 3-4 short
  paragraphs: thesis / why-it-matters / source+credentials / conversational ask),
  senior-PR tone, reporter-aware personalization, fact-base discipline, and SOP
  checklist gates. Adds a newsworthiness verdict before drafting,
  audience-impact framing, real-or-absent personalization (never simulated),
  strategy-level angle regeneration, and an anti-AI-tell validator.
  PORTABLE & LLM-AGNOSTIC: encodes the methodology plus a
  zero-dependency scaffold/validator. No HTTP server, hardcoded LLM, or API keys.
---

# Media Pitch Generator (PR Desk-faithful, LLM-agnostic)

A portable skill that produces publication-ready cold pitch emails and practical
pitch strategy following PR Desk's Pitch Drafter logic plus a product/media-list
SOP. It is designed to be installed into **any** LLM-powered agent (Codex,
Claude Code, WorkBuddy, or a custom agent). There is **no port to expose and no
service to run**. The agent's own model generates the prose; this skill supplies
(1) PR Desk's pitch methodology, (2) a product pitch production SOP, and (3) a
zero-dependency Python scaffold + validator for offline use.

## How this skill works (read this first)
- **You (the installing agent) do the writing.** The `scripts/pitch.py` helper is
  optional: use it to (a) emit a deterministic structure skeleton that you then
  flesh out, and/or (b) validate a draft against PR Desk's hard rules.
- No keys, no network, no OpenAI/Claude calls inside the script. Whatever LLM
  powers you already generates the email. This is what makes the skill installable
  on *any* host unchanged.
- For product launches or technology/consumer products, read
  `references/product-media-pitch-sop.md` when the user asks for strategy,
  media-list alignment, SOP compliance, multiple outreach angles, or checklist
  review. For a quick single pitch, use the embedded workflow below.

## Mandatory question gate before pitch generation

When the user asks this skill to generate, draft, write, revise, or batch-create
a pitch letter, **do not generate the pitch immediately**. First ask a short
series of questions to help the user decide how to proceed. This applies even
when the user has already provided some background materials or a rough brief.
Keep questions practical and easy to answer.

Ask the questions in this order. If the user has already answered a question,
briefly restate the current assumption and ask the user to confirm or correct it:

1. What is the client/company and exact product/service name?
2. What is the one-line launch hook: new release, funding, study, partnership,
   review sample, executive interview, trend commentary, or other?
3. Who is the target reader, and what do they already care about?
4. What pain point does the product solve for that reader?
5. What are the top 3-4 proof points: price, feature, technical spec, clinical
   review, data point, sample availability, launch date, or differentiator?
6. Who can speak for the company, and what are their credentials?
7. What should the journalist do next: include in a story, interview a source,
   test a sample, request images/media kit, or consider a byline?
8. Is this Round 1, follow-up, Tier 2 broad outreach, niche/vertical outreach, or
   a new angle for a different reporter group?
9. Optional: paste one to three past pitches or emails that sound like you, so
   the draft can match your voice. Skip freely if none are handy.

After asking the questions, wait for the user's answer before drafting unless
the user explicitly says to proceed with assumptions. If the user asks to skip
the questions, proceed with the supplied facts and clearly state the assumptions.
If the fact base is weak, write bracketed placeholders for missing facts rather
than inventing.

## Newsworthiness verdict (after the questions, before any drafting)

A generator that cannot say "not a story yet" only ever produces plausible
pitches, never correct decisions. So once the question gate is answered, test
the hook before writing a word. It is weak unless it clears at least three of:

1. **Change/timeliness** — something is new, shifting, or expiring.
2. **Proof** — a number, sample, study, named customer, or verifiable fact.
3. **Stakes** — tension, cost, risk, or a winner/loser; someone should care.
4. **Audience impact** — a specific group in the target outlet's readership is
   affected, and you can say how.

If the hook passes, state a one-line verdict and proceed. If it is weak, do
NOT draft yet: say plainly which tests fail, offer 2-3 concrete strengtheners
(a new data point, a customer proof, a trend peg, a sharper audience), and ask
the user whether to (a) strengthen first or (b) proceed anyway with the
strongest available angle. The user always decides — this is a verdict plus a
question, never a silent refusal.

## Product pitch production SOP

Use this SOP before writing or revising product-oriented pitches:

1. **Product research**: Extract positioning, target audience, features,
   benefits, price, competitors, technical specs, patents, and unique value
   proposition from the provided materials. Treat "best", "first", "fastest",
   "largest", and similar superlatives as high-risk claims that need proof.
2. **Feature -> pain point -> value**: Translate each major feature into the
   reader pain point it solves and the practical benefit for the audience.
3. **Category/article lens**: If tools or user materials are available, identify
   what journalists in the category usually care about: pain points, comparison
   angles, scenarios, price, usability, reviewability, differentiation, and trend
   fit. If unavailable, state the lens as an inference.
4. **Keyword/trend lens**: If Meltwater, search, or user-provided trend data is
   available, use it to identify which topics have momentum. If unavailable, do
   not invent volume numbers; use qualitative relevance only.
5. **Angle selection**: Choose one strongest angle from the journalist's view:
   product launch, industry pain point, scenario/use case, technical
   differentiation, market-trend complement, sample/review invitation, or expert
   interview.
6. **Draft variants when useful**: For batch outreach, produce different angles
   for different reporter groups instead of sending one generic pitch to all.

For the full SOP and media-list logic, see
`references/product-media-pitch-sop.md`.

## PR Desk's pitch logic (encode this in every draft)

**INPUTS the user must provide (ask if missing):**
- **client** + **spokesperson name & title**
- **what you're pitching** — the angle / news hook / why it's timely
- **background materials** (the "upload" step): a pasted press release, data
  points, or notes. Accept pasted text OR a file path; if a file, read it and
  treat its contents as the material. These are the FACT BASE — never invent
  beyond them.
- OPTIONAL **target reporter** + **outlet** for personalization.

**STRUCTURE (proven — follow exactly):**
1. Subject line: a DECLARATIVE statement that reads like a headline (never a question).
2. A short greeting (use the reporter's first name when known).
3. Three to four short paragraphs:
   - **P1**: the thesis / clear news hook in the **FIRST sentence**.
   - **P2**: why it matters — and it must **name who in the outlet's readership
     is affected and how**. Journalists judge relevance by impact on their
     audience's community; generic timeliness prose ("in a fast-moving market")
     fails review. This is the paragraph no data source writes for you — it is
     the editorial judgment connecting the user's fact to the reader's life.
   - **P3**: introduce the source — client + spokesperson + credible title — and what they can offer a reporter.
   - **P4 (optional)**: a conversational, low-friction ask (15-min briefing, bylined idea).
4. Personalization is **real or absent — never simulated**. If a reporter is
   named:
   - With web/search tools (or user-supplied links): reference **ONE specific
     recent piece** of theirs *with its date*, and offer a **COMPLEMENTARY**
     angle that extends their storyline (not generic "I saw your article"
     filler). The complementary angle is the substance; the citation only
     proves you read.
   - Without real coverage in hand: insert a bracketed placeholder like
     `[reference a recent {outlet} piece on {topic} + its date]` for the human
     to fill — **do NOT fabricate** a title, URL, or date.
   - If no genuinely complementary connection exists, **omit personalization
     entirely**: an accurate on-beat pitch with no flattery beats counterfeit
     familiarity. Never open with "I loved your article", "big fan", or
     "I came across your piece".

**TONE**: "sound like you, not a robot" — conversational, confident, concise,
senior-PR-pro; respects the reporter's time; never salesy, never corporate fluff.
If the user provided voice samples (question 9), match their cadence, diction,
and sign-off — but hard rules always override style samples, and never reproduce
a sample's bad habits (flattery openers, hype). What matters most is the
negative: suppress AI-template voice. **Banned AI-tell vocabulary** everywhere:
"excited to share", "revolutionary", "game-changing", "cutting-edge", "delve",
"seamlessly", "in today's fast-paced world".

**HARD RULES**: under 150 words; no bullet points; no attachment mentions; no
inline hyperlinks in the body. Every claim comes from the inputs/materials.

**REGENERATE — change strategy, not wording**: re-rolling the same thesis with
new phrasing only explores the letter's surface; a genuinely different pitch
needs a different angle. When the user asks to regenerate, pick a **different
angle from the SOP angle menu** (product launch, pain point, scenario/use case,
technical differentiation, trend complement, sample/review invite, expert
interview) and — true to this skill's question-driven workflow — ask the user
for whatever input the new angle needs before drafting it. Reserve
same-thesis re-phrasing for explicit wording-only requests. The script's
`--variant N` tags the scaffold with the Nth angle lens from that menu.

## Licensed formula deviations

The structure above is the default scaffold, not a law. When every AI-drafted
pitch converges on the same four-paragraph shape, the shape itself becomes the
tell. Two deviations are licensed — offer them as options and let the user
choose; never switch silently:

- **Ultra-short**: two to three sentences total — hook + ask, nothing else.
  Best for reporters the user already knows or hyper-competitive inboxes.
- **Data-first**: lead with the single strongest number and what it means; one
  supporting paragraph; ask.

Non-negotiables that survive every deviation: fact-base discipline,
real-or-absent personalization, declarative subject, no bullets, no body
links, no attachment mentions. The word cap moves only when the user asks
(`--max-words`).

## Required pre-send checklist

Every final pitch must pass this checklist before delivery:

- **Verdict given**: The newsworthiness verdict was delivered before drafting;
  if the hook was weak, the user chose to strengthen or proceed.
- **Fact base**: All claims come from user materials, cited source text, or a
  clearly stated inference. No invented stats, quotes, reporter articles, or
  superlatives.
- **Hook**: First sentence states the clear news hook or pain-point/value angle.
- **Audience fit**: The pitch explains why this matters to the target outlet's
  readers, not only why the company cares — and P2 names the affected reader
  community specifically.
- **Feature -> value**: Technical specs are translated into practical reader
  value.
- **Proof points**: Includes only the strongest 3-4 facts or benefits.
- **Source**: Names the company and spokesperson with title when provided, and
  states what the source can explain.
- **CTA**: Ends with one low-friction next step: story consideration, briefing,
  interview, sample/review, factsheet/media materials, or byline idea.
- **Reporter personalization**: Real or absent — one real recent piece *with
  its date*, a bracketed placeholder, or personalization omitted entirely.
  Never fabricate coverage or simulate familiarity; no flattery openers
  ("I loved your article", "big fan", "came across your piece").
- **No AI-tells**: None of the banned vocabulary ("excited to share",
  "revolutionary", "game-changing", "cutting-edge", "delve", "seamlessly",
  "in today's fast-paced world"); subject stays within ~9 words / 60
  characters so it survives a mobile inbox.
- **PR Desk hard rules**: Declarative subject, short greeting, 3-4 short
  paragraphs, under 150 words, no bullets, no body links, no attachment mention
  (unless the user opted into a licensed deviation).

When presenting the final answer, include a compact checklist result if the user
asked for SOP compliance or validation.

## Usage

### A. Scaffold with the script, then you write (recommended)
```bash
python3 {SKILL_DIR}/scripts/pitch.py \
  --topic "edge AI cuts retail restocking time in half" \
  --client Acme --spokesperson "Jane Doe" --title "VP Operations" \
  --outlet Wired --reporter "John Smith" \
  --material-text "Acme Q2: 47% faster restocking across 200 stores." \
  --variant 0
# --material PATH  (repeatable) reads a file as background material
# --variant N      (N>0) tags the scaffold with the Nth SOP angle lens —
#                  rebuild P1/P2 around that angle, don't just re-word
# --json           emit raw JSON
```
Take the printed skeleton, then rewrite the prose with your own LLM voice
(following the STRUCTURE / TONE above). The skeleton is a scaffold, not the
final email.

### B. Validate a draft against PR Desk's hard rules
```bash
python3 {SKILL_DIR}/scripts/pitch.py --validate "$(cat my_pitch.txt)"
# checks: declarative subject + subject length, word count (<150), bullets,
# links, attachment mentions, flattery openers, AI-tell vocabulary, and
# coverage references that lack a date or placeholder
```

### C. Library
```python
import sys; sys.path.insert(0, "{SKILL_DIR}/scripts")
from pitch import build_skeleton, validate_pitch, PRDESK_SPEC, PitchInput
sk = build_skeleton(PitchInput(topic="...", client="Acme",
                                materials=["...press release..."]))
issues = validate_pitch(sk.body)   # list of rule violations, [] if clean
```
`PRDESK_SPEC` is the full methodology string — load it into your own prompt when
you generate, so every draft stays faithful to PR Desk.

## Why no port / no hardcoded LLM?
The skill runs *inside* an LLM agent. That agent already has a model, so calling
a second LLM API (or standing up an HTTP server) is redundant and would leak the
user's unpublished pitch context to a third party. Keeping it portable means the
same skill file works on Codex, Claude Code, WorkBuddy, etc. unchanged.

## Notes / limits
- The script's output is a deterministic skeleton (correct structure, generic
  prose with bracketed placeholders). The publication-ready email is written by
  **YOU** (the agent's LLM).
- Facts must come from the user's materials — never invent stats or quotes.
- Reporter personalization needs real coverage; fetch it with your tools or use a
  bracketed placeholder rather than fabricating.
- The user's `topic` / materials are sensitive — don't paste unannounced M&A /
  pre-earnings details into any shared surface.
