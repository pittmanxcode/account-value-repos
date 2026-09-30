# Pay, Time, and Value-Model Methodology

## Compensation (US-equivalent basis, per approved decision)

1. **Preferred source.** US-posted salary ranges in Crunchyroll postings.
   Where present, they are captured in `data/processed/jobs.csv`
   (`salary_hint`) and take precedence.
2. **Default source.** BLS Occupational Employment and Wage Statistics,
   **May 2025** national medians, harvested via O*NET OnLine into
   `data/raw/onet_wages_2025.txt` (BLS blocks automated retrieval directly;
   O*NET republishes the same wage data).
3. **Occupation mapping.** Each of the 77 postings is mapped to a SOC
   occupation and a seniority level (`scripts/02_build_value_model.py`,
   `TITLE_MAP`). Seniority multipliers applied to the occupation median:
   entry 0.80, mid 0.90, senior 1.10, lead 1.25, staff/principal 1.50,
   manager 1.35, director 1.60, executive/GM 2.00.
4. **Non-US postings** (Mexico City, Hyderabad, London, Singapore, Tokyo)
   are valued at hypothetical US-equivalent pay, **not local compensation**,
   per the approved decision. This overstates local cost but aligns with a
   US-based Factory buying decision.
5. **Fully loaded view** = base × 1.30 (benefits, payroll taxes, overhead),
   shown alongside salary-equivalent figures.

## Time model

- **1,920 productive hours per FTE-year** (40 h × 48 weeks). The annual
  capacity, loaded factor, and adoption rates are constants at the top of
  `scripts/02_build_value_model.py` and editable.
- Each posting's 1,920 hours are allocated across responsibility clusters in
  proportion to its extracted responsibility bullets (`bullet_share`). This
  is a transparent proxy for emphasis, not a measured time study; the
  limitation is documented in the README.
- Each cluster carries a descriptive **operational basis** (per ticket,
  per filing cycle, per sprint, per campaign, and so on) and a benchmark
  citation for the underlying activity mix.
- The Japanese-language twin of the Senior Producer posting inherits its
  English twin's cluster distribution.

## Scenario model

`saved_hours = role_hours × addressable_share × net_time_reduction × adoption × (fit_normal / 100)`

| Parameter | Conservative | Base | Upside |
|---|---|---|---|
| Adoption across eligible workflows | 50% | 75% | 90% |
| Net time reduction on addressable time | per cluster, low | per cluster, midpoint | per cluster, high |

- Net time reduction is applied **after** deducting human-review overhead.
  Per-cluster values are anchored to published AI-productivity evidence
  (see `sources.md`) and cluster evidence confidence.
- Addressable share captures the fraction of a cluster's hours an agent
  could own at professional quality at all.
- Bespoke-enabled upside is reported **separately**, scaled only where a
  named integration build exists; it is never blended into the baseline.

## Aggregation caveat

Totals assume **one FTE per open posting** (77 FTE-equivalents). Public
postings do not reveal actual headcount, so portfolio totals represent the
opportunity across open-req equivalents, not company-wide payroll savings.

## Benchmark sources (summary)

| Source | Used for |
|---|---|
| Crunchyroll Greenhouse board (Sep 2026 snapshot) | Postings, verbatim responsibilities |
| BLS OEWS May 2025 via O*NET | US median wages by occupation |
| pandev-metrics 2026 IDE telemetry (3.2 h code, 1.8 h debug, 2.5 h meetings/day) | Software development time basis |
| McKinsey (2023), *The economic potential of generative AI* | Function-level productivity ranges |
| Bain (2025), *From Pilots to Payoff* | Software-engineering acceleration with process change |
| ITIF (2025) survey | Realized AI time savings by frequent users |
| O*NET work-activity structure | Cluster time bases by occupation family |
| Factory documentation (docs.factory.ai) | Normal-setup capability boundary |

Full citations in `sources.md`.
