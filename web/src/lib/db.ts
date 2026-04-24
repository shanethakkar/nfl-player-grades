/**
 * Postgres client, shared across server components and API routes.
 *
 * Uses the `postgres` package (faster than `pg` for serverless). Keep the
 * client singleton so Next.js's hot reload doesn't open a new pool per edit.
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
    max: 10,
    idle_timeout: 20,
  });

if (process.env.NODE_ENV !== "production") {
  globalThis.__sql = sql;
}
