# Agent Integration — Media Pitch Generator (portable, no port)

This skill is designed to drop into **any** LLM-powered agent unchanged. There is
no HTTP server to run and no LLM to call from inside the skill — the host agent
supplies the model. This file explains how to wire it up in the common hosts.

## What the skill gives the agent
- `SKILL.md` — the full PR Desk pitch methodology (inputs, structure, tone, hard
  rules, personalization, regenerate). The agent loads this and follows it.
- `scripts/pitch.py` — a **zero-dependency** (stdlib-only) Python helper that:
  - `build_skeleton(inp)` → emits a deterministic structure skeleton with
    `[bracketed]` placeholders for the agent to fill.
  - `validate_pitch(text)` → checks a draft against PR Desk's hard rules
    (declarative subject, <150 words, no bullets / links / attachment mentions).
  - `PRDESK_SPEC` → the methodology string, ready to load into the agent's own prompt.

## Codex / Claude Code / custom CLI agent
1. Place this skill folder where your agent reads skills.
2. When the user asks for a pitch, follow `SKILL.md`. Gather inputs (ask for the
   background materials if missing).
3. Optionally run the scaffold:
   `python3 {SKILL_DIR}/scripts/pitch.py --topic "..." --client Acme --material-text "..."`
4. Write the email with your own model, following the STRUCTURE / TONE / RULES.
5. Validate: `python3 {SKILL_DIR}/scripts/pitch.py --validate "$DRAFT"`.

## WorkBuddy
Same as above — the SKILL.md is loaded automatically; call the script via the
Bash tool for the scaffold/validator, or import `build_skeleton` / `validate_pitch`
from `scripts/pitch.py` in a Python step.

## Why no port / no hardcoded LLM
- The agent already has an LLM; a second LLM call (or a server) is redundant.
- It avoids leaking the user's unpublished pitch context (client, angle, materials)
  to a third-party API.
- A single skill file works across hosts with zero per-host changes.

## Optional: grounding the reporter personalization
If the host agent has web/search tools, fetch the reporter's recent coverage and
reference one real piece. If it does not, emit a bracketed placeholder instead of
fabricating a title or URL. The skill never calls a search API itself.
