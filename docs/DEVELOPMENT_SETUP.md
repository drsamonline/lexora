# LEXORA Development Setup

> **Status:** Draft (developer workflow for the docs-only phase is real; code-phase steps are planned)
> **Owner:** Documentation architect (delegated)
> **Related:** [BUILD_GUIDE.md](BUILD_GUIDE.md) · TESTING_GUIDE.md *(Batch E)* · CONTRIBUTING.md *(Batch E, repo root)* · [NEXT_SESSION.md](NEXT_SESSION.md)

## Purpose & scope

Getting a contributor productive today (documentation work) and after P1-T1 (code work). Distinguishes verified-now from planned.

## Today: documentation-only development (verified 2026-10-15)

```text
git clone <repo>            # OQ-6 pending: no remote exists yet; work in local checkout
cd <repo>
python3 scripts/linkcheck.py        # must print ALL INTERNAL LINKS OK
git status --short                  # inspect before committing
```

Conventions enforced by session discipline (CI will formalize these in Batch E):
1. Five-file checkpoint rule (master prompt §1.6): after ~5 modified files, review diffs + commit.
2. Every material decision → ADR; index row in DECISIONS.md same session.
3. Continuity quartet (STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION) updated at session end — non-negotiable.
4. No fabricated claims: statuses describe repo reality.

Branch note: current working branch is tool-created (`qwen-code-*`); long-lived branch strategy is part of OQ-6.

## After P1-T1: code development (planned)

```text
python -m venv .venv && . .venv/bin/activate   # Python range per OQ-7
pip install -e ".[dev]"                         # planned extra with pytest/linters/fuzzer
python -m pytest                                # run layers per TEST_STRATEGY
pre-commit hooks (proposed once linters chosen via ADR)
```

Environment expectations to record when first captured: interpreter version, library versions, OS, peak-RSS harness output.

## Repository layout (as it exists / as planned)

| Path | Exists? | Purpose |
|---|---|---|
| `LEXORA_Full_Blueprint_Design_Master_Prompt.md` | ✅ | Source-of-truth blueprint |
| `docs/**`, `scripts/linkcheck.py` | ✅ | Documentation system + checker |
| `.github/**` | ❌ planned (Batch E, only with real workflows) | CI/templates |
| `lexora/`, `tests/`, `pyproject.toml` | ❌ planned (P1-T1) | Package + suite |
| `benchmarks/` | ❌ planned (P2) | Manifests, env captures, reports |

## Debugging aids (planned)

- `lxz` CLI verbose/diagnostic flags documented only in CLI_REFERENCE once implemented.
- Logging design pre-documented in LOGGING_AND_DIAGNOSTICS.md (Batch D) so implementation has a target.

## What not to do

- Don't add dependencies before DEPENDENCY_POLICY (Batch D) and OQ-7 land.
- Don't edit frozen artifacts (golden vectors, manifests) without an ADR bumping the relevant version identifier.
