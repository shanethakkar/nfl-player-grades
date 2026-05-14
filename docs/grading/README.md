# Grading Documentation

Design playbooks, research notes, audit reports, and checklists for the v1+ grading system. The consumer-facing methodology lives at [../methodology.md](../methodology.md); ADRs (per-position formula decisions) live at [../adr/](../adr/).

## What's here

| File | What it is |
|---|---|
| [audit-playbook.md](audit-playbook.md) | The methodology for designing/auditing a position formula — skill-tree mapping, redundancy check, YoY noise check, weight sizing |
| [iteration-workflow.md](iteration-workflow.md) | **Canonical** shipping workflow for weight changes (preview → sync → regrade). ~30s end-to-end |
| [data-inventory.md](data-inventory.md) | Which nflverse source has which column. Check before proposing any new component |
| [pending.md](pending.md) | Queue of open audit / methodology tasks |

### `checklists/`
| File | What it is |
|---|---|
| [checklists/add-position.md](checklists/add-position.md) | 13-step process for adding a new graded position |
| [checklists/removing-a-component.md](checklists/removing-a-component.md) | DELETE-orphan workflow when dropping a component from a formula |

### `research/`
Per-position research notes from audits and revisions. Each file documents what was considered, what was rejected, and why.

| File | Position(s) |
|---|---|
| [research/cb-grading.md](research/cb-grading.md) | CB v1 + Safety v1 implementation notes |
| [research/defensive-grading.md](research/defensive-grading.md) | EDGE / iDL / LB v1 lessons (OLB-gap, rate inflation, thresholds) |
| [research/rb-v1-1.md](research/rb-v1-1.md) | RB v1.1 (rb_catch_pct removed) |
| [research/wr-v1-1.md](research/wr-v1-1.md) | WR v1.1 (drop_rate in, fumble_rate out) |
| [research/te-v1-1.md](research/te-v1-1.md) | TE v1.1 + WR v1.2 (self-audit, both at −0.05 drop_rate) |

### `audits/`
Dated diagnostic audits across the whole system.

| File | What it is |
|---|---|
| [audits/2026-05-14-cross-position-yoy.md](audits/2026-05-14-cross-position-yoy.md) | YoY noise check on every component × position. Flagged 3 noise components; all shipped as v1.x revisions |
| [audits/2026-05-14-correlation.md](audits/2026-05-14-correlation.md) | Pairwise correlation matrix per position. Found QB EPA↔success_rate at r=0.88 (strongest redundancy) and other overlaps |
| [audits/2026-05-14-validity-baseline.md](audits/2026-05-14-validity-baseline.md) | Downstream predictive validity baseline. Composite-grade vs next-year Pro Bowl correlation per position. iDL strongest (+0.46), LB weakest (+0.18). Targets to beat for any future weight change. |

## Quick start

- **Want to ship a weight change?** Read [iteration-workflow.md](iteration-workflow.md).
- **Auditing a new component idea?** Read [audit-playbook.md](audit-playbook.md), then check [data-inventory.md](data-inventory.md) for source availability.
- **Adding a whole new position?** Read [checklists/add-position.md](checklists/add-position.md).
- **Need to understand why a weight is what it is?** Look in [research/](research/) for that position, then check the relevant ADR in [../adr/](../adr/) for the formal decision record.
