---
name: work-backlog-item
description: Work one backlog item end to end — spec, specialist implementation, independent adversarial verification, the repository's declared checks, documentation, and a draft pull request per repository — following orchestration workflow W12. Trigger on "work T-nnn", "next up T-nnn", "close T-nnn", "work the next backlog item".
---

# Work a backlog item

Thin trigger for **W12 — Backlog item to reviewed pull request** in
[`../../orchestration/workflows.md`](../../orchestration/workflows.md). The depth is there and in
the handoff contracts in [`../../orchestration/handoffs.md`](../../orchestration/handoffs.md);
this skill only fixes the entry conditions and the stopping point.

## Input

- An item id (`T-nnn`) or "next": the first open item of the current phase in the repository's
  `TODO.md`. An item whose status line says Done is skipped, not redone.
- The repository's root `CLAUDE.md`. It declares the checks that define *done*, the sibling
  repositories that must move in the same change set, and the actions that are never taken
  without a human. Read it before step 0; it overrides anything generic here.

## Run W12

0. **Scope.** Quote the item. Check `REVIEW.md`: if a human decision blocks it, write or update
   the entry and stop with the question. Do not implement around a missing decision.
1. **Specify** in a scratch file: files to change, contract or convention impact (and therefore
   which siblings change), acceptance checks, what must not be touched, the verifier to use.
2. **Implement** through the specialist the routing table names for the area. Mirrored files
   are edited once and copied byte-identically.
3. **Verify** through a *different* specialist with the implementer → verifier envelope. The
   verifier edits nothing and returns severities, evidence, fixes and a verdict.
4. **Fold** every BLOCKER and SHOULD-FIX; re-verify only what changed.
5. **Check** on the final tree: every command the root `CLAUDE.md` lists, plus the sibling diff
   when a shared file changed. Anything that cannot run here is reported as *not run*, with the
   step that runs it first.
6. **Record**: `CHANGELOG.md`, the item's status in `TODO.md` (date, what landed, where), a
   `REVIEW.md` entry for any human action or decision the change now depends on, `CLAUDE.md`
   when a convention or cross-repository contract changed. Every number in these must match the
   diff.
7. **Deliver**: one commit per logical change, pushed to the designated branch of each
   repository; a draft PR per repository with the evidence, what was not run, each human gate as
   `[REVIEW REQUIRED]`, and the merge order when it matters. Then stop and hand the human the
   exact remaining steps.

## Never

- Merge, approve, or mark ready without being asked.
- Apply infrastructure, deploy, roll back, or flip a live setting.
- Commit before the verifier has reported, or push a tree the checks have not seen.
- Route around a host limitation (no API, no daemon, no repository access): say which step is
  blocked and what the human does instead.
