# Next Session Resume Card

**Last verified state:** 2026-10-15, after Batch A creation **and link validation** (`ALL LINKS OK`; one broken link in docs/index.md found and fixed). Re-verify with git before trusting.
**Current phase:** Phase 0.2 — Batch A drafted & validated; only the commit checkpoint remains.
**Branch/commit:** `main` @ `816f58f` is HEAD; all Batch A files are untracked/uncommitted as of writing this card.
**Working-tree state (at time of writing):** ~22 new untracked documentation/config files; blueprint untouched.
**Last completed task:** Created all Batch A documents + ran link/fabrication validation (link-check script, badge grep).
**Current blocker:** Owner input on OQ-1…OQ-10 ([docs/DECISIONS.md](DECISIONS.md)) blocks Batch B normative spec. Commit itself awaits owner workflow confirmation (§1.6: "if the user's workflow permits").
**First action next session:** Run the verification commands below and confirm they match this card; if clean, commit Batch A (or record why not), then proceed to "Tasks in order".

## Read first
- [ ] [docs/STATUS.md](STATUS.md)
- [ ] Latest entry of [docs/SESSION_LOG.md](SESSION_LOG.md) (Session 2)
- [ ] [docs/DECISIONS.md](DECISIONS.md) — check whether owner answered any OQ-*
- [ ] Skim created Batch A files for link integrity

## Tasks in order
1. Confirm working tree still matches this card (`git status --short`).
2. Commit Batch A with message `docs: Batch A — governance and navigation foundation` (only if owner workflow permits committing; otherwise record the non-commit reason in SESSION_LOG).
3. Record the new hash (`git rev-parse --short HEAD`) in PROGRESS.md checklist, STATUS.md, and a Session 3 log entry.
4. **If owner has answered any OQs:** draft corresponding ADRs from the template, mark Accepted, and reflect changes in affected docs. Then begin Batch B planning.
5. **If no answers yet:** optionally draft *Proposed* ADRs recommending resolutions for OQ-1…OQ-4 (do NOT mark accepted), then stop and await owner.

## Acceptance criteria
- [x] Every relative link in every created .md resolves to an existing file (verified 2026-10-15: `ALL LINKS OK`).
- [x] No badges, no invented commands/results anywhere (verified by grep; re-run below to confirm).
- [ ] Batch A committed (or non-commit reason recorded in SESSION_LOG).
- [ ] STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION mutually consistent post-commit.

## Commands to run
```text
cd /workspace
git status --short                      # expect only untracked doc files (pre-commit)
git log --oneline -3
find . -name "*.md" -not -path "./.git/*" | sort
python3 - <<'EOF'                       # quick relative-link checker (proposed helper, not project tooling)
import os,re
bad=[]
for r,d,fs in os.walk('.'):
    if '.git' in r: continue
    for f in fs:
        if f.endswith('.md'):
            p=os.path.join(r,f)
            for m in re.finditer(r'\]\(([^)#]+?)(?:#[^)]*)?\)', open(p,encoding='utf-8').read()):
                t=m.group(1)
                if t.startswith(('http','mailto:')): continue
                q=os.path.normpath(os.path.join(r,t))
                if not os.path.exists(q): bad.append(f'{p}: {t}')
print('\n'.join(bad) or 'ALL LINKS OK')
EOF
```

## Do not repeat
- Session 1 audit (complete — findings live in DECISIONS.md OQ table and SESSION_LOG).
- Directory scaffolding for docs/ADR and docs/templates (exists).
- Do not create Batch B–E placeholder files early; master prompt forbids empty placeholders.

## Risks/open decisions
- OQ-1…OQ-4 unresolved → SPECIFICATION.md must remain unwritten until resolved (Batch B risk if started prematurely).
- License/repo URL unknown → README stays badge-free; do not add `.github/` workflows yet.

## Required documentation updates at session end
- SESSION_LOG.md (new dated entry: actions, commands, outcomes, hash if any)
- STATUS.md (phase/batch table, blockers)
- PROGRESS.md (checklist ticks, metrics)
- NEXT_SESSION.md (rewritten resume card)
- CHANGELOG.md (Unreleased section)
- README.md only if public-facing state changed
