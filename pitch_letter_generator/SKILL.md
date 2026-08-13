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
  checklist gates. PORTABLE & LLM-AGNOSTIC: encodes the methodology plus a
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

After asking the questions, wait for the user's answer before drafting unless
the user explicitly says to proceed with assumptions. If the user asks to skip
the questions, proceed with the supplied facts and clearly state the assumptions.
If the fact base is weak, write bracketed placeholders for missing facts rather
than inventing.

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
   - **P2**: why it matters (timeliness / the "so what").
   - **P3**: introduce the source — client + spokesperson + credible title — and what they can offer a reporter.
   - **P4 (optional)**: a conversational, low-friction ask (15-min briefing, bylined idea).
4. If a reporter is named, reference **ONE specific recent piece** of theirs and
   offer a **COMPLEMENTARY** angle (not generic "I saw your article" filler).
   - If you have web/search tools, fetch a real recent piece. If not, insert a
     bracketed placeholder like `[reference a recent {outlet} piece on {topic}]`
     for the human to fill — **do NOT fabricate** a title/URL.

**TONE**: "sound like you, not a robot" — conversational, confident, concise,
senior-PR-pro; respects the reporter's time; never salesy, never corporate fluff.

**HARD RULES**: under 150 words; no bullet points; no attachment mentions; no
inline hyperlinks in the body. Every claim comes from the inputs/materials.

**REGENERATE**: if the user wants a different angle, change the hook/lead while
keeping the same structure (the script's `--variant N` also tags the scaffold).

## Required pre-send checklist

Every final pitch must pass this checklist before delivery:

- **Fact base**: All claims come from user materials, cited source text, or a
  clearly stated inference. No invented stats, quotes, reporter articles, or
  superlatives.
- **Hook**: First sentence states the clear news hook or pain-point/value angle.
- **Audience fit**: The pitch explains why this matters to the target outlet's
  readers, not only why the company cares.
- **Feature -> value**: Technical specs are translated into practical reader
  value.
- **Proof points**: Includes only the strongest 3-4 facts or benefits.
- **Source**: Names the company and spokesperson with title when provided, and
  states what the source can explain.
- **CTA**: Ends with one low-friction next step: story consideration, briefing,
  interview, sample/review, factsheet/media materials, or byline idea.
- **Reporter personalization**: If a specific reporter is named, reference one
  real recent piece or use a bracketed placeholder. Never fabricate coverage.
- **PR Desk hard rules**: Declarative subject, short greeting, 3-4 short
  paragraphs, under 150 words, no bullets, no body links, no attachment mention.

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
# --json           emit raw JSON
```
Take the printed skeleton, then rewrite the prose with your own LLM voice
(following the STRUCTURE / TONE above). The skeleton is a scaffold, not the
final email.

### B. Validate a draft against PR Desk's hard rules
```bash
python3 {SKILL_DIR}/scripts/pitch.py --validate "$(cat my_pitch.txt)"
# prints: declarative subject? word count (must be <150), bullets? links? attachments?
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
