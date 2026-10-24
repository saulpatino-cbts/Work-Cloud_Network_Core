# Design — batch offline export/import (BUILD-03)

**Status:** Draft for review. No implementation yet.
**Requirements:** `requirements.md`. Decisions (2): reuse `cna discover` + zip
checkpoints; newest-by-timestamp merge; no-secrets hard rule + optional
encryption flag.

## Overview

A **batch record** is a portable zip of one or more discovery checkpoints plus a
manifest. Export produces it offline (no live appliance needed); import drops its
checkpoints into an online engagement's checkpoint set so the existing topology
reassembly includes them as if discovered live. The seam is deliberate and small:
the platform already persists one checkpoint per subscription/account and
rebuilds topology from them, so a batch record is essentially those checkpoint
files, carried and merged.

Grounded in the code:
- `EngagementStore.write_discovery_checkpoint()` writes
  `discovery/<platform>_<id>.json` (one per source).
- `load_aws_topology()` / `load_azure_topology()` reassemble `AWSTopology` /
  `AzureTopology` from `_load_checkpoints()` over `discovery/<platform>_*.json`.
- `DiscoveryCoverageReport` (`cna/core/discovery_coverage.py`) already models
  which sources succeeded/were blocked — the place to note "imported offline".

## The batch record format

A zip:
```
batch-record-<label>-<ts>.zip
├── manifest.json
└── checkpoints/
    ├── aws_<account_id>.json         (an AWSRegionTopology dump)
    └── azure_<subscription_id>.json  (an AzureSubscriptionTopology dump)
```

`manifest.json`:
```
schema_version    e.g. "1.0.0" (matched to TOPOLOGY_SCHEMA_VERSION on import)
exported_at       ISO-8601
label             human label (customer/engagement name — not a secret)
checkpoints: [
  { platform: "aws"|"azure", source_id, filename, sha256, discovered_at }
]
encrypted         bool (optional encryption flag)
```

No credentials, no secrets — the checkpoints are topology dumps only (R3/R4).
The manifest's per-checkpoint `sha256` is the integrity + idempotency key.

## Export (offline) — R1

Decision: **reuse `cna discover`**. Offline, an operator runs the existing
discovery against a local checkpoint-only store (`CNA_DATA_DIR` pointed at a
local dir); that writes the same `discovery/<platform>_<id>.json` files. Export
then packages selected checkpoints:

New `cna/core/batch_record.py`:
```python
def export_batch_record(store, engagement_id, source_ids, out_path, *, encrypt=False, key=None) -> Path:
    # read the named checkpoints, strip nothing (they carry no secrets by design),
    # compute sha256 each, write manifest.json + checkpoints/, zip, optional encrypt
```

A new CLI verb `cna batch export` wraps it (the CLI is the offline entry point).
Optional encryption (flag): if `--encrypt`, the zip is wrapped with the same
AES-256-GCM scheme the platform already uses (`cna/core/credential_crypto.py`)
under an operator-supplied passphrase — the manifest records `encrypted: true`.
The hard rule stands regardless: no secret is ever inside the record.

## Import (online) — R2, R3

New in `batch_record.py`:
```python
def import_batch_record(store, engagement_id, record_path, *, key=None,
                        conflict="newest") -> ImportResult:
    # 1. open (decrypt if encrypted), load manifest
    # 2. validate: schema_version compatible, platform known, each checksum matches
    # 3. for each checkpoint: resolve target path discovery/<platform>_<source_id>.json
    # 4. idempotency + conflict:
    #      - if target absent -> write it
    #      - if present and identical sha256 -> skip (idempotent re-import, R2.3)
    #      - if present and different -> conflict policy (default "newest":
    #        compare discovered_at, keep the newer, note the replacement)
    # 5. record the source as imported-offline in the coverage report (R3.3)
```

Because step 3 writes the checkpoint into the engagement's own
`discovery/<platform>_<id>.json` — exactly where live discovery writes it — the
downstream `load_*_topology` reassembly, analysis, reports and the beehive pick
it up with **no special-casing** (R3.1). The imported source's `source_id` is
preserved (R2.4), so cross-source connectivity (a peering between an imported
subscription and an online one) renders as an ordinary edge (R3.2 / beehive R3).

A new CLI verb `cna batch import` wraps it.

## Integrity & safety — R4

- **Checksum verify** per checkpoint before it is written; a mismatch or a
  truncated zip aborts the whole import with a clear message (R4.1). No partial
  import — validate all, then write all.
- **Data, not code:** each checkpoint is parsed as JSON and constructed through
  the pydantic `AWSRegionTopology` / `AzureSubscriptionTopology` models, which
  reject unknown shapes; nothing from the record is executed (R4.2).
- **Schema version:** import refuses a record whose `schema_version` is
  incompatible with the appliance's `TOPOLOGY_SCHEMA_VERSION`, with a message
  naming both versions (R2.2).
- **No secrets:** export writes only topology dumps; import validates the
  manifest has no credential fields. The optional encryption protects the record
  in transit but is not a substitute for the no-secrets rule.

## Conflict policy (decision: newest-by-timestamp)

When an imported `source_id` already exists online (the same subscription scanned
both ways), the default `conflict="newest"` keeps the checkpoint with the newer
`discovered_at` and records the replacement in the coverage report. A
`conflict="refuse"` option is available for an operator who wants to be asked.

## Testing strategy (synthetic fixtures only)

- **Round-trip:** export two synthetic checkpoints → import into a fresh store →
  `load_*_topology` returns both sources; the beehive graph spans them.
- **Idempotency:** importing the same record twice yields one copy, not two
  (R2.3).
- **Conflict:** import a newer checkpoint over an existing source → newer wins +
  coverage note; `refuse` mode aborts.
- **Integrity:** a tampered checksum / truncated zip is refused; no partial
  write (R4.1).
- **Schema guard:** an incompatible `schema_version` is refused with both
  versions named.
- **No-secrets:** export of a checkpoint containing (synthetic) secret-looking
  fields strips/rejects — assert the record carries only topology.
- **Encryption round-trip:** `--encrypt` export then decrypt-import returns the
  same checkpoints; wrong key fails cleanly.
- **Attribution:** imported source keeps its `source_id`; a cross-source peering
  renders as a beehive edge.

## Cross-repo note

This is Core-only (CLI + core persistence). The appliances do not change — they
already consume whatever topology the engagement store holds. No appliance
notification needed (per the cross-repo rule, this is not shared-surface).

## Open questions carried to the user (from requirements)

1. Offline scan method — reuse `cna discover` + zip (this design assumes it).
2. Conflict policy — newest-by-timestamp (this design's default).
3. Encryption — no-secrets hard rule + optional `--encrypt` flag (this design).

All three are the recommended defaults; flagged here so a different call is a
cheap design edit before build.
