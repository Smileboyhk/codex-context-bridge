## Codex Context Bridge handoff rules

This repository uses Codex Context Bridge (CCB) so a separate ChatGPT web conversation can accurately understand the current project state.

After any meaningful development/research phase:

1. Update `STATE.md`.
2. Keep **Implemented** and **Verified** separate. Never call something verified only because code exists.
3. Record important architecture/product choices in `DECISIONS.md`.
4. Run the real configured verification commands.
5. Preserve the latest user-visible/runtime evidence (PNG, screenshots, HTML, metrics JSON, logs selected for sharing) at paths matched by `.ccb.toml`.
6. Run:

   ```text
   ccb snapshot --run-checks
   ```

   If `[sync].target` is configured, run:

   ```text
   ccb snapshot --run-checks --sync
   ```

7. Before ending, report the path to `.ai-context/CHATGPT_ENTRY.md`.

Evidence discipline:

- Runtime/visual output is stronger evidence than a status note.
- Automated checks are stronger evidence than an implementation claim.
- A failed check must remain failed in the handoff.
- If something was not tested, label it **not verified**.
- Do not place secrets, `.env` contents, credentials, private keys, access tokens, or personal data in AI handoff documents.
