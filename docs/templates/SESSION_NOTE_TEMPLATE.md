# Session Note Template

Copy this block into `docs/SESSION_LOG.md` at the end of every session (append-only; never edit past entries except via a marked `CORRECTION` entry).

```markdown
## YYYY-MM-DD — Session N: <short objective>

- **Objective:** <what this session set out to do; link to NEXT_SESSION task if resuming>
- **Pre-state verified:** <git status / HEAD hash / anything that proves the starting point>
- **Actions / files changed:**
  - <exact paths, created/modified/deleted>
- **Commands run & results:** <actual commands; actual exit codes/outcomes — no assumed results>
- **Tests:** <suite run? pass/fail counts from real output, or "no test tooling exists">
- **Decisions:** <ADRs drafted/accepted, or "none"; update docs/DECISIONS.md accordingly>
- **Failures/blockers encountered:** <honest list or None>
- **Known gaps left open:** <what is intentionally unfinished>
- **Next action:** <one sentence; must match the rewritten NEXT_SESSION.md>
```

## Rules
- Record commit hashes only after they exist (`git rev-parse --short HEAD`).
- If nothing was verified, write "Not verified" rather than implying success.
- Keep each entry under ~40 lines; deep detail belongs in design docs, not the log.
