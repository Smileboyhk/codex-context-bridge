# Prompt to give Codex when adding CCB to an existing project

Copy this prompt into Codex from the target repository:

```text
We are adding Codex Context Bridge (CCB) to this repository so a separate ChatGPT web conversation can accurately understand the project after each development phase.

Do not change business logic just to make the handoff look successful.

1. Read the repository's existing AGENTS.md, STATE.md, README.md, current planning/handoff documents, and test instructions first.
2. Confirm `ccb` is installed. If not, install Codex Context Bridge from the local clone with:
   python -m pip install -e <PATH_TO_CODEX_CONTEXT_BRIDGE> --no-build-isolation
3. Run `ccb init` only if `.ccb.toml` does not already exist. Preserve existing STATE.md / DECISIONS.md content.
4. Configure `.ccb.toml` using REAL paths from this repository:
   - project objective / current phase
   - important context documents
   - real focused test/build/evaluation commands
   - latest user-visible/runtime artifacts (PNG/JPG/HTML/JSON metrics etc.)
   - narrow source_pack globs for the modules ChatGPT may occasionally need
5. Append the rules from Codex Context Bridge `templates/AGENTS_SNIPPET.md` to this repo's AGENTS.md, adapting wording without weakening evidence rules.
6. Update STATE.md so Implemented and Verified are separate. Record current blockers and exact next step.
7. Run the project's real verification commands.
8. Run:
   ccb snapshot --run-checks
   Add --include-source only if the next ChatGPT review needs implementation detail.
   Add --sync if [sync].target has been configured.
9. Inspect `.ai-context/CHATGPT_ENTRY.md`, CHECKS.md and ARTIFACTS.md. If a check failed, keep it failed. If artifacts are stale/missing, fix the artifact configuration instead of pretending success.
10. Finish by reporting:
   - the exact `.ai-context/CHATGPT_ENTRY.md` path
   - check status
   - artifact count
   - current Git commit
   - anything still not verified
```
