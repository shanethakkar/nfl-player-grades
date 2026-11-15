/**
 * Postgres client, shared across server components and API routes.
 *
 * Uses the `postgres` package (faster than `pg` for serverless). Keep the
 * client singleton so Next.js's hot reload doesn't open a new pool per edit.
 *
 * `prepare: false` is required for Neon's pooled endpoint (PgBouncer).
 * `max: 1` keeps each serverless instance to a single connection so a
 * burst of invocations cannot exhaust the pooler (the previous `max: 10`
 * correlated with CONNECT_TIMEOUT / auth-timeout errors under crawl load).
 * `idle_timeout: 20` drops idle connections quickly between invocations.
 */

import postgres from "postgres";

declare global {
  var __sql: ReturnType<typeof postgres> | undefined;
}

const connectionString = process.env.DATABASE_URL;

if (!connectionString) {
  throw new Error("DATABASE_URL is not set. Copy web/.env.local.example to web/.env.local.");
}

export const sql =
  globalThis.__sql ??
  postgres(connectionString, {
    prepare: false,
    max: 1,
    idle_timeout: 20,
  });

if (process.env.NODE_ENV !== "production") {
  globalThis.__sql = sql;
}
