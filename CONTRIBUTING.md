# Contributing to LEXORA

> **Project status: design & documentation phase.** No implementation code exists yet. This guide reflects how the project is actually run today (documentation batches with strict honesty rules) and what will change when code lands.
> **Last verified:** 2026-10-15 against repository commit `7969155`.

## What this project is (and is not)

LEXORA is a text-cleaning and exact-compression system being built through a staged documentation foundation (Batches A–E) before any code. Read [README.md](README.md) and [docs/STATUS.md](docs/STATUS.md) first — they state honestly what is real versus planned.

The authoritative design source is [LEXORA_Full_Blueprint_Design_Master_Prompt.md](LEXORA_Full_Blueprint_Design_Master_Prompt.md).

## Ground rules (non-negotiable)

1. **Honesty over polish.** Never claim a feature, test, benchmark, build, audit, or commit succeeded unless it actually ran and was verified. Never fabricate numbers, contacts, SLAs, CI runs, or badges.
2. **No placeholder files.** Do not create empty or stub documents/files "for later." If something doesn't exist yet, link-checkable prose says so (see the status legend in [docs/index.md](docs/index.md)).
3. **Don't claim improvement before measurement.** Compression-gain statements are prohibited until a reproducible held-out benchmark under the frozen protocol ([docs/BENCHMARK_PROTOCOL.md](docs/BENCHMARK_PROTOCOL.md)) demonstrates them. [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md) must stay empty of numbers until then.
4. **Never commit credentials.** Tokens, keys, and passwords do not go into commits, remote URLs, or docs. If a token appears in output by accident, scrub it and record the correction in [docs/SESSION_LOG.md](docs/SESSION_LOG.md).
5. **Security ≠ implemented.** Nothing is hardened yet; see [SECURITY.md](SECURITY.md) for reporting and [docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md) for design intent only.

## Development workflow (current reality)

Work proceeds in dated sessions on documentation batches, tracked in [docs/PROGRESS.md](docs/PROGRESS.md):

1. Start by reading [docs/NEXT_SESSION.md](docs/NEXT_SESSION.md), [docs/STATUS.md](docs/STATUS.md), and the latest entry of [docs/SESSION_LOG.md](docs/SESSION_LOG.md).
2. Verify repo state first: `git status --short && git log --oneline -3 && git remote -v`.
3. Make changes per the conventions in [docs/DEVELOPMENT_SETUP.md](docs/DEVELOPMENT_SETUP.md) (including commit-message style currently in use: `docs: <scope> — <summary>`; formal Conventional Commits adoption is pending decision OQ-9 in [docs/DECISIONS.md](docs/DECISIONS.md)).
4. Run the one existing check before committing:

   ```bash
   python3 scripts/linkcheck.py   # must print: ALL INTERNAL LINKS OK (exit 0)
   ```

5. Update continuity files at session end: SESSION_LOG (append-only), STATUS, PROGRESS, NEXT_SESSION, CHANGELOG (Unreleased), and docs/index.md if links changed.
6. Commit. Pushes to the hosted repository require owner-supplied credentials; record push outcomes truthfully (including failures).

There is no test suite, linter, or CI configured yet. Do not add CI workflows or badges until they would actually run and pass (that is Batch E policy, enforced by honesty rule #1 above).

## Branching and pull requests

- `main` holds the latest reviewed state that has been merged locally/pushed by the owner.
- Session work happens on topic branches (e.g. batch branches) and reaches `main` via fast-forward merges or PRs reviewed by the owner.
- Use the PR template at [.github/pull_request_template.md](.github/pull_request_template.md); answer every section honestly — "not run" is an acceptable and expected answer for checks that don't exist yet.
- Issues: use the templates in [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/). Search existing issues first.

## Contribution ideas that are useful right now

- Owner review feedback on drafted documents (Batch D especially — see docs/STATUS.md blockers).
- Answers or delegations for open questions OQ-5…OQ-10 in [docs/DECISIONS.md](docs/DECISIONS.md).
- Documentation errors: point out any statement that contradicts verified reality; corrections are appended to SESSION_LOG, never rewritten into history.

When Phase 1 code begins (blocked on OQ-7 Python version), this file will gain environment setup, test commands (`pytest` etc.), and code-review requirements. Until then, any instructions implying those exist would be false, so they are absent by design.

## Code of conduct / scope reminders

- Similarity alone must never trigger automatic deletion of text. Compression is not encryption. See non-goals in [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md).
- Privacy rules for corpus/dictionary data: [docs/PRIVACY_AND_DATA_HANDLING.md](docs/PRIVACY_AND_DATA_HANDLING.md).

Questions? Open an issue — there is no other contact channel, and inventing one would violate rule #1.
