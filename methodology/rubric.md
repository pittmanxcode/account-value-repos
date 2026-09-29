# Factory Fit Scoring Rubric

## Deployment boundary

Two boundaries are scored separately and never blended:

1. **Normal setup (primary score).** What Factory can do with ordinary
   configuration: repository and document access, approved connectors,
   terminal and browser tooling, Missions, automations, and a human approval
   step before consequential actions.
2. **Bespoke-enabled score.** The same boundary plus a concrete, named
   integration build (custom connector, MCP server, internal-API workflow,
   skill, or evaluation harness) with a human checkpoint. Bespoke capability
   is never treated as already available; every uplift row names the required
   build and its internal dependency.

## Weighted dimensions (0–100)

| Dimension | Weight | What it measures |
|---|---|---|
| Digital/task executability | 25 | Is the work digital and well-defined enough for an agent to execute? |
| Match to Factory-supported workflows | 25 | Does it map to coding, analysis, documentation, automation, QA, and agent orchestration? |
| Required input & system access | 15 | Can the needed systems be reached under normal access, or via a named bespoke build? |
| Output verifiability | 15 | Can quality be checked mechanically (tests, diffs, reconciliation) plus human review? |
| Professional-quality attainability with human review | 15 | Could output pass as experienced-professional work after review? |
| Risk & governance constraints | 5 | Regulatory, legal, or safety limits on agent execution. |

## Hard penalties (applied in cluster scores)

- Unavailable internal systems or data
- Physical work and on-site presence
- Relationship ownership and negotiation
- Executive judgment and strategic sign-off
- People management, coaching, and trust-building
- Taste-led final decisions (brand, creative)
- Legal, security, or tax professional sign-off

## Score interpretation

| Band | Meaning |
|---|---|
| 85–100 | Factory can own the workflow end-to-end; human reviews output |
| 70–84 | Factory owns execution; human directs and approves |
| 50–69 | Strong assistance; human owns the work, agent lifts productivity |
| 30–49 | Support-only: research, drafting, logistics |
| 0–29 | Not suitable for agent execution |

## Evidence confidence

- **High** — activity is code/data-first with mechanical verification
- **Medium** — digitizable but depends on system access or review quality
- **Low** — assumptions dominate (relationship, physical, taste-driven work)
