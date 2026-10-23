# Tasks — batch offline export/import (BUILD-03)

**Status:** Draft for review. No implementation yet.
**Requirements:** `requirements.md`. **Design:** `design.md`.

Core-only (CLI + `cna/core`). All customer data is topology; no secrets in a
record. Synthetic fixtures only in tests.

- [x] 1. `cna/core/batch_record.py` — `BatchManifest` / `CheckpointEntry` models + checksum helper. _(R1, R4)_
- [x] 2. `export_batch_record(...)` — selected checkpoints, checksum each, manifest + checkpoints/, zip, optional AES-256-GCM (scrypt) wrap. _(R1)_
- [x] 3. `import_batch_record(...)` — open/decrypt, validate (schema + platform + per-checkpoint checksum), validate-all-then-write-all, idempotent on source+sha, newest-by-timestamp (or `refuse`). _(R2, R3, R4)_
- [x] 4. CLI `cna batch export` / `cna batch import` (`cna/cli/batch.py`, registered in `main.py`). _(R1, R2)_
- [x] 5. Coverage report: `DiscoveryCoverageReport.imported_offline` + `note_imported_offline()` mark offline-imported sources distinctly (idempotent, sorted); `ImportResult.offline_source_ids()` feeds it. Tested. _(R3.3)_
- [x] 6. Tests — `tests/unit/test_batch_record.py` (14): round-trip, idempotency, conflict (newest + refuse + older-no-replace), integrity (tampered/truncated refused, no partial write), schema guard, encryption round-trip + wrong-key + missing-passphrase, empty-export. _(R1–R4)_
- [x] 7. CHANGELOG entry. _(done)_

## Verification

- "Done" = tasks 1–7 complete; tests green against synthetic fixtures; an
  exported record imports into a fresh store and `load_*_topology` returns the
  imported sources unified with any existing ones; re-import is idempotent; a
  tampered record is refused with no partial write.
- No live appliance or cloud account is required — the whole capability is
  checkpoint files + zip + merge, fully testable offline.
