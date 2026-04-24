# 0005 - Hand-written TS types with codegen guardrail

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

The DB schema is the source of truth (ADR 0001). The Next.js side needs
TypeScript types that match the schema. We considered:

1. **Hand-write everything.** Simple but rots silently when migrations
   change.
2. **Switch to Drizzle/Prisma**, define schema in TS, generate everything.
   Wrong direction — would make TS the source of truth.
3. **Auto-generate from the live DB** with `kanel` / `pg-to-ts`, replace
   hand-written types entirely.
4. **Hand-write the public types, auto-generate the raw row types as a
   guardrail.**

## Decision

**Option 4.** Two layers:

- `web/src/types/db.generated.ts` — auto-generated from
  `information_schema` by `nflgrades gen-types`. Mirrors raw table shapes
  one-to-one. Never edited by hand. Committed to the repo so TS compiles
  without a live DB.
- `web/src/types/index.ts` — hand-written. Imports the generated row types
  and re-exports them with curated names, narrowed string-literal unions
  (e.g. `"AFC" | "NFC"` instead of `string`), and view-shaped types for
  joins and aggregates.

In CI we'll run `nflgrades gen-types --check` which exits non-zero if the
generated file is stale. That's the guardrail: if you change a migration
without regenerating, CI catches it.

## Consequences

**Easier:**
- The schema can grow without TS imports breaking — add a column, run
  gen-types, decide whether to expose it in `index.ts`.
- We get string-literal unions (`Conference`, `DataTier`) where the raw
  Postgres type is just `text`/`smallint`. Better than what any pure
  generator gives us.
- Reviewers see the type changes in `index.ts` PRs and can reason about
  the public API surface.

**Harder:**
- Two files to keep mentally aligned. Mitigated by `index.ts` being short
  and `db.generated.ts` being mechanical.
- `gen-types` requires a live DB. Acceptable since we have docker-compose.

**Explicitly given up:**
- Fully automatic types. We're trading a small amount of manual work for
  the ability to express domain types more precisely than introspection
  can give us.
