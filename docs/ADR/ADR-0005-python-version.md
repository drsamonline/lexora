# ADR-0005: Supported Python version range for the prototype

> **Status:** Accepted 2026-10-15 by documentation-architect delegation (owner directive "decide ADRs yourself" / repeated "continue"+"start" with no objection after Session 12 recommendation; revocable by owner — resolves OQ-7)
> **Date:** 2026-10-15
> **Deciders:** Documentation architect (delegated); owner may supersede
> **Related:** [DECISIONS.md](../DECISIONS.md) OQ-7 · [PHASES.md](../PHASES.md) P1 prerequisites · [BUILD_GUIDE.md](../BUILD_GUIDE.md) · [DEVELOPMENT_SETUP.md](../DEVELOPMENT_SETUP.md)

## Context / Problem

The blueprint says "Python-first" but pins no version. This blocks the dependency policy, `pyproject.toml`, and any future CI matrix (OQ-7). The development container runs **Python 3.12.10**; the key runtime dependency `zstandard` ships cp312 wheels on PyPI (verified installed: `zstandard 0.25.0`, 2026-10-15). Low-resource target users may have older distro Pythons.

## Options considered

- **A.** `>=3.9` — maximum reach, but no wheel-matrix verification exists for 3.9–3.11 in this project; untested claims are prohibited.
- **B.** `>=3.12,<4.0` — exactly matches the verified environment; every claim we can make is backed by a real run here.
- **C.** Pin to the exact interpreter (`==3.12.10`) — maximally reproducible for benchmarks, too rigid for users.

## Decision

Adopt **B** as the supported range: **Python >=3.12,<4.0**, with benchmark reproducibility additionally pinned via captured `env.json` (interpreter build + library versions) per BENCHMARK_PROTOCOL §6. If the owner later requires older-distro support, widen to A only after installing and running the full test suite under each added version (evidence before claim).

## Consequences and trade-offs

- (+) `pyproject.toml` `requires-python = ">=3.12,<4.0"` states only what has been executed.
- (+) Type-hint syntax and `tomllib` usable without backports.
- (−) Users on 3.8–3.11 distros must install a newer Python; acceptable for prototype stage.

## Security / performance / compatibility impact

None beyond version availability; keeps us on a CPython branch receiving security fixes.

## Implementation and test implications

- `pyproject.toml` declares the range; tests run under 3.12.10 locally until CI exists (OQ-6/CI deferred until runnable).
- Benchmark results artifacts must record the exact interpreter version string.
