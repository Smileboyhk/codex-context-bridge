---
name: codex-context-bridge
summary: Generate an evidence-based handoff from a local coding project so ChatGPT web can continue product and technical reasoning after Codex work.
---

# Codex Context Bridge Skill

Use this skill at the end of a meaningful coding/research phase when work needs to continue in a separate ChatGPT conversation.

## Procedure

1. Read `.ccb.toml`, `STATE.md`, `DECISIONS.md`, and the repository's own `AGENTS.md`.
2. Finish the requested development work first.
3. Update `STATE.md` with separate Implemented / Verified / Blockers / Next step sections.
4. Ensure `.ccb.toml` artifact globs point at actual current outputs, not stale examples.
5. Run the project's relevant tests/build/evaluation.
6. Run `ccb snapshot --run-checks` (plus `--sync` when configured).
7. Inspect `.ai-context/CHECKS.md` and `.ai-context/ARTIFACTS.md`; never claim success if they disagree.
8. Return `.ai-context/CHATGPT_ENTRY.md` as the handoff entry point.

Use `--include-source` only when the next ChatGPT task genuinely needs implementation detail and the configured source globs are narrow enough to review safely.
