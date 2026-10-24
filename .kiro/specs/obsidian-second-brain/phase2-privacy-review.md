# Isolation note — Obsidian beehive (BUILD-02 Phase 2)

**Status:** Superseded by the single-customer deployment model (user direction
2026-10-23). Phase 2 is **no longer gated on a cross-tenant privacy review** —
see "Why the gate is removed" below. Kept as the record of why.

---

## Why the gate is removed

The original draft of this document gated Phase 2 on preventing a cross-customer
data leak in a shared "second brain." That risk **cannot occur** under the
deployment model the user confirmed:

> This tool serves exactly **one customer** at all times. One customer may have
> multiple subscriptions, tenants, or accounts — and those belong together — but
> **two separate customers are never in one appliance.** Each customer deploys
> their own appliance.

So there is no multi-customer surface inside an appliance. The isolation boundary
is the **appliance deployment itself**, enforced by how the product is shipped,
not by anything the retrieval code must do. There is no global vault, no
cross-customer retrieval path, because there is no second customer to leak to.

## What replaces the gate

The design concern flips from *separation* to *unification*: a single customer's
**multiple subscriptions / tenants / accounts must be tied together** into one
view, correctly. That is the opposite problem — see the revised Phase 2 scope in
`requirements.md` and the new batch offline import capability
(`.kiro/specs/batch-offline-import/`). The real risks there are:

- **Wrong-merge:** data from subscription A mistakenly attributed to subscription
  B within the same customer. Controlled by keying every record to its source
  subscription/tenant/account id and never collapsing those ids on merge.
- **Stale/duplicate merge:** importing the same offline record twice. Controlled
  by an idempotent import keyed on the source id + a record checksum.
- **Secrets in an exported record:** an offline batch record must carry topology,
  not credentials. Controlled by the same no-secrets rule Phase 1 already applies
  to vault notes.

These are correctness/data-integrity concerns, not cross-tenant privacy. They do
**not** require a human privacy-review gate; they require the merge tests listed
in the revised `tasks.md`.

## Residual note for a future multi-customer idea

If the product ever moves to a shared/multi-customer deployment (explicitly NOT
the current model), this cross-tenant review must be reinstated before that
change ships. Recording it here so the reasoning is not lost.
