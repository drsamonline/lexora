# ADR-0011: GUI distribution — process separation, not in-process linking

> **Status:** **Accepted 2026-10-29** by explicit owner choice (option B when the distribution question was put as a multiple-choice decision).
> **Date:** 2026-10-29
> **Deciders:** Owner Dr Sohil Momin
> **Related:** [DEPENDENCY_LICENCE_REVIEW.md](../DEPENDENCY_LICENCE_REVIEW.md) (the review this decides) · [ADR-0009](ADR-0009-license-polyform-noncommercial.md) (PolyForm Noncommercial, whose Consequences §3 left this open) · [ADR-0008](ADR-0008-gui-toolkit-architecture.md) (toolkit + in-process architecture — **partly superseded**, see Consequences) · [RELEASE_PROCESS.md](../RELEASE_PROCESS.md) R3

## Context / Problem

ADR-0009 relicensed the project to PolyForm Noncommercial 1.0.0 and flagged one item it would not close by itself: the optional `[gui]` extra links PySide6/Qt, which is LGPL-3.0. The review in [DEPENDENCY_LICENCE_REVIEW.md](../DEPENDENCY_LICENCE_REVIEW.md) found no licence conflict — LGPL requires relinkability, notices and a documented replacement route, all of which dynamic linking satisfies — and set out four ways to distribute the GUI. The owner has chosen **process separation**.

## Decision drivers

- **Licence clarity.** A separate process that talks to the core over a defined interface is the strongest possible answer to "can the user replace the LGPL parts?": the GUI is not linked into the compression engine at all.
- **Failure isolation.** A Qt crash cannot corrupt an in-flight archive operation if the operation happens in another process.
- **The interface already exists.** The CLI is the app's real API — seven subcommands with documented exit codes, JSON reports and a stable refusal taxonomy. A GUI that drives it needs no new contract.
- **Testability here and now.** The core side of the boundary is testable without Qt, which is exactly the constraint this project's agent environment has.

## Options considered

- **A. Comply and ship in-process** (NOTICE + licence texts + About-view notice + relinking statement). Cheapest, and legitimate — but leaves LGPL obligations attached to every distributed build and keeps the GUI inside the engine's failure domain.
- **B. Process separation** — **chosen.** The GUI invokes the CLI as a subprocess; the core stays a plain program.
- **C. Drop `[gui]` from distribution.** Zero obligations, but the GUI stops being a shipped artifact.
- **D. Commercial Qt licence.** Removes the obligations with money rather than architecture.

## Decision

**The GUI is a client of the CLI, not a library consumer of the core.**

1. Every pack, unpack, canon, verify, inspect and batch operation the GUI performs runs as a subprocess invocation of the installed `lexora` entry point, with arguments and exit codes as documented in [CLI_REFERENCE.md](../CLI_REFERENCE.md).
2. `src/lexora/gui/` may still import **pure, Qt-free formatting helpers** (e.g. `lexora.inspect.summarize`/`format_report`) for display, because those are read-only and carry no engine behaviour. It must **not** import `lexora.container` or `lexora.canonicalize` to *perform* work.
3. Long-running operations stream through the subprocess's stdout/stderr; progress and cancellation use the CLI's existing semantics (per-file reporting, exit codes) rather than a second protocol invented for the GUI.
4. `LICENSE` (PolyForm, with its `Required Notice:` line) still ships with every artifact — RELEASE_PROCESS R3 is unchanged. The LGPL notices from the review's §4 checklist become **optional rather than mandatory** for the GUI artifact, since the LGPL libraries are no longer part of the distributed program; shipping them anyway is harmless and recommended.
5. The About view keeps naming the toolchain (PySide6, ADR-0008), so a user can see what the GUI is built on.

## Consequences & trade-offs

**Positive.** The LGPL question is answered structurally rather than by paperwork, and stays answered if the GUI's dependencies change again. The GUI gets crash isolation and the core gets a single, documented interface. The boundary is testable without Qt: the "does the GUI drive the CLI correctly" half can be tested against the real CLI, which is what this environment can run.

**Negative / accepted risks.** Process-per-operation costs a Python interpreter start (~50–100 ms) per invocation — acceptable for file operations measured in hundreds of milliseconds or more, and avoidable later with a long-lived `lexora serve` mode if it ever bites. Streaming progress is coarser than in-process callbacks unless the CLI grows a machine-readable progress stream. And this **partly supersedes ADR-0008**: its decisions 2–3 assumed an in-process service layer calling the library; the `service.py` adapter remains, but its job changes from "call the library" to "build argv and parse results". ADR-0008's toolkit choice (PySide6) and the Qt-free-core constraint are untouched.

**Explicitly not claimed:** nothing here is implemented yet. No GUI code changed in this session, because PySide6 cannot be installed in the agent environment (no `libegl1`, no apt) and shipping untested widget code would be worse than shipping none.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | Slightly improved: the GUI's process can no longer corrupt in-flight engine state, and the engine's attack surface is reached only through documented CLI arguments |
| Performance / memory | +50–100 ms per operation (interpreter start); peak RSS per operation unchanged, and Qt's memory is now in a separate process that can be reaped |
| Compatibility (format/spec) | None — no format, no archive byte changes |

## Implementation & test implications

Order of work when a Qt-capable environment exists:
1. Replace `AppService.run_pack/run_unpack/...` bodies with subprocess calls (argv built from the same validated settings); keep the `JobResult` shape so the window code barely changes.
2. Keep the existing golden-parity test but re-aim it: **GUI output == CLI output** is now true by construction, and the test should assert the argv built for each operation instead.
3. Add tests that run **without Qt** against the real CLI: argument construction, exit-code → banner mapping, and cancellation killing the child process cleanly (no orphan, no partial artifact — the CLI already writes atomically).
4. Only then touch widgets (batch queue, drag-drop), which is the part that genuinely needs a display.
