# Architecture

CCB intentionally separates **claims** from **evidence**.

## Inputs

### Controlled human/Codex documents
Configured in `[documents].include` and read with per-file size limits.

Typical files:

- README.md
- AGENTS.md
- STATE.md
- DECISIONS.md
- ROADMAP.md
- focused research/planning handoffs

### Git evidence
Read locally with Git CLI:

- current branch and HEAD
- remote origin
- dirty status
- unstaged and staged diff stats
- recent commit list

### Verification evidence
Commands are never discovered or executed automatically. Only commands explicitly configured under `[[checks]]` may run, and only when `--run-checks` is passed.

### Runtime evidence
Configured glob patterns select real output files. Current matches are copied into the snapshot folder; old copied artifacts are removed before each new snapshot.

### Optional source evidence
Source files are excluded from the pack by default. `--include-source` activates only the globs explicitly listed under `[source_pack].include`, subject to file and total character limits.

## Outputs

`CHATGPT_ENTRY.md` is the stable entry point. It intentionally stays short and tells ChatGPT which evidence to trust and what to read next.

`PROJECT_SNAPSHOT.md` provides a human-readable full handoff, while `PROJECT_SNAPSHOT.json` is the machine-readable equivalent.

`CHECKS.md` and `ARTIFACTS.md` prevent project-state prose from silently becoming “proof”.

`SOURCE_INDEX.md` gives the model structural awareness without uploading source code.

`SOURCE_PACK.md` is optional and should be used narrowly.

## Sync model

CCB does not authenticate to cloud vendors. It performs an atomic-ish local folder replacement into a user-configured cloud-sync directory. Google Drive for Desktop, OneDrive, Dropbox or another sync client can then handle transport.

This keeps cloud credentials out of CCB and makes the generated folder easy to audit before sharing.

## Threat model

CCB is designed to reduce accidental leakage, not to replace a dedicated secret-scanning/DLP product.

Defenses include:

- refusing common secret-bearing filenames and private-key suffixes;
- basic token/API-key redaction;
- root-bound file selection;
- explicit document/source/artifact allowlists;
- no network calls;
- no command execution unless `--run-checks` is explicitly requested.

Users should still inspect snapshots from sensitive repositories before sharing them externally.
