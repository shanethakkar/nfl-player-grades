# Web

Next.js 15 (App Router) app that reads from Postgres and renders teams,
depth charts, and player grades.

## Setup

```bash
cd web
cp .env.local.example .env.local
npm install
npm run dev
```

Visit http://localhost:3000.

## Layout

```
web/
├── src/
│   ├── app/              # App Router routes
│   │   ├── page.tsx                # landing: 32-team grid
│   │   ├── teams/[abbr]/page.tsx   # team page: roster + depth chart
│   │   ├── players/[id]/page.tsx   # player page: season + career grades
│   │   ├── methodology/page.tsx    # how grades are computed
│   │   └── api/                    # API routes (read-only JSON)
│   ├── components/                 # React components
│   ├── lib/                        # DB client, query helpers, formatters
│   ├── types/                      # shared TS types mirroring the DB schema
│   └── styles/                     # globals.css (Tailwind)
└── public/                         # static assets (logos, etc.)
```

## Conventions

- **Server components by default.** Only mark `'use client'` when you need
  interactivity.
- **All DB access goes through `src/lib/db.ts`.** No ad-hoc `postgres()`
  constructors in routes.
- **Types mirror the DB schema.** Keep `src/types/index.ts` in sync with
  `db/migrations/`.
- **Tailwind for styling.** No CSS-in-JS in v1.
