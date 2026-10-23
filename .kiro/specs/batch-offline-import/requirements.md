# Requirements — batch offline export/import (BUILD-03)

**Status:** Draft for review. New capability from user direction 2026-10-23.
**Relates to:** BUILD-02 beehive R3 (unify one customer's multiple
subscriptions/tenants). Tracking issue to be created.

## Why we are doing this

One customer may have several subscriptions, tenants, or accounts. Some of those
may be scanned **offline** — from a disconnected environment, a separate
operator, or an account the online appliance cannot reach directly. The user
wants to:

> export a **batch record** (an offline record) from one place, import it into an
> online appliance, and have it **tie the subscriptions/tenants together as if
> they were both discovered online.**

So the appliance's unified network view (the beehive, reports, analysis) includes
the offline-scanned subscription exactly as if it had been discovered live.

## Key facts from the codebase

- Discovery already persists **one checkpoint per subscription/account**:
  `discovery/<platform>_<id>.json`, each an `AWSRegionTopology` or
  `AzureSubscriptionTopology` dump (`cna/core/persistence.py`
  `write_discovery_checkpoint` / `load_aws_topology` / `load_azure_topology`).
- The full topology is **reassembled from those per-source checkpoints** at
  analysis time — there is no single persisted topology blob.

This is the natural seam: a "batch record" is one (or more) of these per-source
checkpoints, packaged for transport, and "import" is dropping it into the target
engagement's checkpoint set so the existing reassembly picks it up.

## Glossary

- **Batch record** — a portable, offline bundle containing one or more discovery
  checkpoints (per subscription/tenant/account) plus a manifest describing what
  it holds and where it came from.
- **Online appliance** — a deployed appliance with a live engagement store.
- **Source id** — the subscription id / tenant id / account id a checkpoint came
  from. The key that keeps records attributed correctly on merge.

## Requirements

### R1 — Export a batch record offline
**As an** operator scanning a subscription/tenant offline, **I want** to export
its discovery as a self-contained batch record, **so that** it can be carried to
an online appliance.

Acceptance criteria:
1. THE SYSTEM SHALL export a batch record containing the selected discovery
   checkpoint(s) and a manifest with: schema version, platform (aws/azure),
   source id(s), engagement/customer label, export timestamp, and a checksum per
   checkpoint.
2. THE batch record SHALL be a single portable file (e.g. a zip) that needs no
   network or live appliance to produce.
3. THE batch record SHALL contain **topology only** — no credentials, no secrets
   (same rule as the beehive vault).

### R2 — Import a batch record into an online appliance
**As an** engineer, **I want** to import a batch record into a live engagement,
**so that** the offline-scanned subscription joins the online topology.

Acceptance criteria:
1. WHEN a batch record is imported into an engagement, THE SYSTEM SHALL place its
   checkpoint(s) into that engagement's checkpoint set so the existing
   `load_aws_topology` / `load_azure_topology` reassembly includes them with no
   special-casing downstream.
2. THE import SHALL validate the manifest (schema version, platform, checksums)
   and refuse a corrupt or version-incompatible record with a clear message.
3. THE import SHALL be **idempotent**: importing the same record twice (same
   source id + checksum) SHALL not duplicate the subscription in the topology.
4. THE import SHALL preserve each checkpoint's **source id**, so a node stays
   attributed to its true subscription/tenant/account after the merge.

### R3 — Tie the sources together as if discovered online
**As an** engineer, **I want** the imported subscription unified with the online
ones, **so that** cross-subscription connectivity is visible and analysis treats
them as one customer's estate.

Acceptance criteria:
1. AFTER import, the beehive, reports, and analysis SHALL treat the imported
   source identically to a live-discovered one (it flows through the same
   reassembly + analysis path — no "imported" second-class handling).
2. Cross-source connections (a peering/TGW/VPN between an imported subscription
   and an online one) SHALL render as edges in the beehive (BUILD-02 R3).
3. The discovery coverage report SHALL note which sources were imported offline
   vs discovered live, as a data-quality caveat (mirrors
   `cna/core/discovery_coverage.py`).

### R4 — Integrity and safety
Acceptance criteria:
1. A batch record SHALL carry a checksum per checkpoint; import SHALL verify it
   and refuse a tampered or truncated record.
2. Import SHALL never execute content from the record — it is data (topology
   JSON), validated against the topology schema, never code.
3. No secret SHALL be exportable in, or importable from, a batch record.

## Out of scope

- Live two-way sync (this is a one-way offline export → online import).
- Cross-**customer** merge (one customer per appliance; this unifies one
  customer's own sources only).
- Re-running discovery from the record (it carries already-discovered topology,
  not credentials to re-scan).

## Open questions for the user

1. **Who runs the offline scan?** Does the offline side run the existing
   `cna discover` against a checkpoint-only local store (so a batch record is
   literally its `discovery/` checkpoints zipped), or is there a separate offline
   collector? (Recommendation: reuse `cna discover` locally, zip the
   checkpoints — minimal new code, exact same data shape.)
2. **Merge conflict policy** if an imported source id already exists online
   (same subscription scanned both ways): newest-by-timestamp wins, or refuse and
   ask? (Recommendation: newest-by-timestamp, with the coverage report noting the
   replacement.)
3. **Encryption of the batch record at rest** during transport — required, or is
   "no secrets inside" sufficient? (Recommendation: no-secrets is the hard rule;
   offer optional encryption as a flag.)
