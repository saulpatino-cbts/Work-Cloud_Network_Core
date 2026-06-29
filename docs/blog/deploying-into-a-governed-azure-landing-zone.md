# What a Governed Azure Landing Zone Teaches You (the Hard Way)

*2026-06-29 · Field notes from the first end-to-end CNA dev deploy*

There's a particular kind of humbling that only happens when you deploy your
carefully-written Terraform into a subscription that **someone else governs**. Your
config is "correct" in isolation. It plans cleanly. And then it dies — not because your
code is wrong, but because the Azure Landing Zone around it has opinions you didn't
account for.

We just walked a CNA deployment from "crashes on the first resource" to "running" across
ten distinct failures. Almost none of them were bugs in the usual sense. They were
**collisions with governance** — and the lessons generalize to any ALZ deploy.

## The mental model that would have saved us a day

A governed ALZ is not an empty subscription you own. It's a subscription wrapped in
**management-group policies** that:

- **auto-create resources** you didn't ask for (diagnostic settings via DeployIfNotExists),
- **deny** resources that violate guardrails (secret validity windows),
- **enable protections** you can't turn off (Key Vault purge protection),

…all enforced from a scope **above** your subscription, by an identity hierarchy **above**
your deploy principal.

Once you internalize that, the failures stop looking random. They're all variations of
one theme: **the platform already owns this, and your IaC is competing instead of
deferring.**

## Lesson 1: Don't manage what the platform already manages

Our firewall deploy hung for ten minutes (firewalls are slow), and in that window an ALZ
**DeployIfNotExists** policy created a diagnostic setting on it — at the exact moment our
Terraform tried to create *its own* diagnostic setting on the same resource. Result: a
false "already exists / needs to be imported into State."

Our first instinct was a `time_sleep` — wait for the policy to settle, then create ours.
But you can't win a race against a 10-minute resource with a fixed sleep. The real fix
was conceptual, not mechanical: **stop managing diagnostic settings at all.** On an ALZ,
the policy owns them. Logs still flow — to the central workspace the org runs. We set
`manage_diagnostic_settings = false` and the whole class of error vanished.

> If the platform creates it for you, deleting your version of it from your IaC is not a
> regression — it's correct. Dual-ownership is the bug.

## Lesson 2: Your deploy identity is not you

We had a clever pre-flight: "scan the management groups, detect the ALZ diagnostics
policy, and tell Terraform to stand down." It ran every deploy and confidently reported
**"No ALZ policy detected."**

Except there was one. The script ran as the **deploy service principal**, which couldn't
read management groups. *We* could see them from our laptop; the SP couldn't. So the
detection scanned a single scope, found nothing, and **failed open** — defaulting to
"manage diagnostics," which is exactly what caused Lesson 1's collision.

The takeaway is brutal and useful: **any logic that "detects the environment and adapts"
must run as an identity that can actually read the environment.** If it can't, it will
quietly choose the unsafe default. We deleted the detection dependency and used a safe
static default instead. Less clever, far more reliable.

## Lesson 3: Soft-delete makes static names a liability

Azure soft-deletes Cognitive Services accounts and Key Vaults on deletion, and **reserves
their names** for a retention period. Our teardown did `az group delete` (soft-delete) and
then immediately wiped the Terraform state. The next deploy found:

- a soft-deleted AI account holding the name → `409 ... must purge it first`,
- Key Vault secrets that survived in a recovered vault but were gone from state →
  "already exists."

Two fixes, two philosophies. For the AI account (no purge protection): set the provider
feature `purge_soft_delete_on_destroy = true` so Terraform frees the name on destroy. For
the Key Vault (purge protection **on**, by tenant policy — *cannot* be purged for 90
days): you can't purge, so you **recover** the same-named vault instead
(`recover_soft_deleted_key_vaults = true`).

> Static resource names + soft-delete + a teardown that wipes state faster than Azure
> finishes deleting = a guaranteed collision on the next deploy. The durable fix is in
> the teardown sequencing, not the deploy.

## Lesson 4: Governance denies are a feature, listen to them

An App Insights secret got a flat `403 ForbiddenByGovernancePolicy — Secrets should have
the specified maximum validity period`. The org's Key Vault guardrail requires every
secret to expire within a maximum window, and ours set 90 days without the lifecycle
handling the others had.

We *could* have chased the exact allowed window. But the deny prompted a better question:
**did we even need this resource?** App Insights was provisioned and wired into every
container — and the application code never read it. It was dead telemetry infrastructure.
We removed it entirely. The governance deny didn't just block a bad config; it surfaced
something we should have deleted anyway.

> A policy deny is the platform telling you something about your design. Sometimes the
> fix is to comply. Sometimes it's to realize you were provisioning something pointless.

## Lesson 5: The non-ALZ bugs are still waiting for you

Not every failure was governance. Once the infra applied, we hit a string of ordinary CI
bugs that ALZ just happened to expose because we finally got that far:

- A container image variable was empty because `$GITHUB_ENV` **doesn't cross jobs** — the
  resolved image was set in one job and read in another. (Use job `outputs`.)
- `az rest --body @file` doesn't default `Content-Type` (only inline JSON strings do) →
  `415`. A one-flag fix.
- A heredoc emitted broken JSON for a container `args` entry → deserialization error.
- A freshly-created Container Apps Job's managed identity returned a transient `500`
  during sidecar warmup, and our validation fetched the token **single-shot** with no
  retry.

None of these are ALZ-specific. They're the kind of latent CI fragility that only
surfaces when you stop failing early. Each one was a small, surgical fix — but you only
*reach* them by clearing the governance collisions first.

## The pattern underneath all of it

Every failure, ALZ or not, reduced to one of a few recognizable shapes:

- **"already exists / needs import"** → state and reality disagree, or the platform owns
  the resource you're creating.
- **`403 disallowed by policy`** → a guardrail; read the named `policyAssignment`.
- **`409 soft-deleted`** → a reserved name; purge or recover.
- **"detection chose wrong"** → your logic lacks the RBAC to see what it's detecting.
- **empty cross-job value** → `$GITHUB_ENV` instead of `outputs`.
- **transient `500` from a fresh resource** → warmup; retry with backoff.

Once you can name the shape, the fix is usually small. The expensive part is the mindset
shift: on a governed ALZ, **you are a guest in someone else's house.** Defer to the
platform, assume your identity sees less than you do, and treat every policy deny as
information rather than an obstacle.

---

*Full failure-by-failure catalog with commits and fixes:
[alz-deployment-runbook.md](../alz-deployment-runbook.md). The architectural decision on
diagnostics and observability ownership:
[ADR 0001](../adr/0001-diagnostics-and-observability-on-alz.md).*
