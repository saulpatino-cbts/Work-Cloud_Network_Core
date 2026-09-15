# App / TypeScript area review — Finding records

Area: `app-typescript` (`apps/cna-web`, Next.js/TypeScript). Produced by task 5.1
of the `production-readiness` spec (verify-then-close-gaps). Each record maps to the
`cna.review.model.Finding` shape (`area`, `severity`, `proposed_action`, `dedup_key`,
`subject`, `blocker_id`) so the task-14 consolidation engine can ingest it. All entries
here are **fixable** app-area findings (no `blocker_id`); the AWS-view alignment escalation
boundary is handled separately by task 5.2.

Severity scale mirrors `Severity`: INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL.

## Findings

### F-APP-001 — Raw backend `detail` forwarded to client surfaces (FIXED)

- **severity:** MEDIUM
- **dedup_key:** `app-typescript:raw-backend-detail-passthrough`
- **subject:** `apps/cna-web/app/api/engagements/[id]/chat/route.ts`,
  `apps/cna-web/app/(dashboard)/engagements/[id]/cloud-credentials/actions.ts` (`testAwsConnection`),
  `apps/cna-web/app/(dashboard)/engagements/[id]/client-deliverables/actions.ts` (`publishClientPortal`)
- **proposed_action:** Route every backend-supplied `detail` through a single web-boundary
  sanitizer (`sanitizeBackendDetail`) that collapses raw/multi-line SDK text to one bounded
  line and falls back to a generic message when detail is empty. The internal API already
  sanitizes its own 502 paths, but the web layer previously trusted that unconditionally and
  applied no length bound, so a 422 validation detail or any future backend detail could reach
  a client surface verbatim. Relates to Requirement 2.3.
- **status:** Applied. Added `sanitizeBackendDetail` to `lib/summarize-error.ts` and wired it
  into the three boundaries above.

### F-APP-002 — `summarizeErrorText` only recognized Azure error text (FIXED)

- **severity:** LOW
- **dedup_key:** `app-typescript:sanitizer-azure-only`
- **subject:** `apps/cna-web/lib/summarize-error.ts`
- **proposed_action:** Generalize the shared summarizer so it also unwraps a JSON `detail`
  field (FastAPI's error envelope) in addition to `error.message`/`message`, and expose an
  explicit `MAX_LEN` bound. Keeps the Azure `AuthorizationFailed` hint while making the helper
  safe to reuse across AWS and chat surfaces.
- **status:** Applied.

### F-APP-003 — `any` cast on Auth.js error `type` discriminant (FIXED)

- **severity:** LOW
- **dedup_key:** `app-typescript:auth-error-any-cast`
- **subject:** `apps/cna-web/lib/auth.ts`
- **proposed_action:** Replace `(error as any).type` with an `unknown`-narrowed accessor
  (`(error as { type?: unknown }).type`) so the logger stays type-safe under `strict` mode.
- **status:** Applied.

## Verified compliant (no finding recorded)

- **Error boundaries present.** `app/global-error.tsx` (root-layout last-resort boundary) and
  `app/(dashboard)/error.tsx` (dashboard route-segment boundary) both exist, log the error
  digest server-side, and render a sanitized, digest-only message to the user. No additional
  boundary gap found.
- **Server-side structured error capture.** `instrumentation.ts` `onRequestError` emits a
  single JSON line (level, message, digest, stack, route) so a user-reported digest correlates
  with the real message in logs. Raw detail stays server-side.
- **Floating promises are guarded.** Client fire-and-forget calls (`chat-panel.tsx` suggestion
  buttons and submit) use `void send(...)`; async server actions are awaited. No unhandled
  rejection path found in the reviewed surfaces.
- **API-call error paths already sanitized.** `lib/metrics-api.ts`, `analysis/actions.ts`,
  `documents/actions.ts`, `deliverables/actions.ts`, and `client-deliverables/actions.ts`
  (AI-generation paths) log raw errors with `console.error` and return generic, user-safe
  messages — matching Requirement 2.3.
- **`discovery/actions.ts` job error text.** Raw backend body stored in `errorMessage` is always
  rendered through `summarizeErrorText` in `connections-panel.tsx`, so the client surface is
  bounded. Verified compliant.
- **`as any` style casts.** The `makeStyle(...) as any` pattern in presentation/findings pages
  is a deliberate, localized workaround for the `react/forbid-dom-props` lint rule on dynamic
  widths, not a type-safety gap in application logic. No change made.
