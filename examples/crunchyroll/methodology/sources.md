# Sources & Citations

All sources accessed September 29, 2026.

## Primary

1. **Crunchyroll job board** — https://www.crunchyroll.com/about/jobs
   (77 postings reported at snapshot time; count reconciled exactly).
2. **Greenhouse public board API for Crunchyroll** —
   https://boards-api.greenhouse.io/v1/boards/crunchyroll/jobs?content=true
   Raw snapshot: `data/raw/greenhouse_board_snapshot.json`
   (971 KB, 77 postings, full descriptions).

## Compensation data

3. **U.S. Bureau of Labor Statistics, Occupational Employment and Wage
   Statistics (OEWS), May 2025** national medians —
   https://www.bls.gov/news.release/ocwage.t01.htm
   (direct access blocked for automated retrieval; harvested via O*NET).
4. **O*NET OnLine occupation summaries** (BLS wage data, employment,
   projections) — https://www.onetonline.org/ — harvested for 30 occupation
   codes into `data/raw/onet_wages_2025.txt`. Example:
   https://www.onetonline.org/link/summary/15-1252.00

## Time-use and AI-productivity benchmarks

5. **pandev-metrics (2026).** "How Much Time Developers Actually Code,
   Debug, and Meet" — IDE-tracked: 3.2 h coding, 1.8 h debugging, 2.5 h
   meetings per day. https://pandev-metrics.com/docs/blog/how-much-developers-actually-code
6. **McKinsey Global Institute (2023).** "The economic potential of
   generative AI: The next productivity frontier." Function-level uplift
   ranges used to anchor scenario acceleration.
   https://www.mckinsey.com/capabilities/tech-and-ai/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier
7. **Bain & Company (2025).** "From Pilots to Payoff: Generative AI in
   Software Development." https://www.bain.com/insights/from-pilots-to-payoff-generative-ai-in-software-development/
8. **ITIF (2025).** Survey of generative-AI time savings among frequent
   users (20.5% report 4+ hours saved weekly).
   https://itif.org/publications/2025/05/09/frequent-generative-ai-users-report-significant-time-savings/
9. **O*NET work-activity structure** by occupation family — basis for
   cluster time-basis descriptions.

## Factory capability boundary

10. **Factory documentation** — https://docs.factory.ai/llms.txt
    Missions, Droid CLI, automations, connectors/MCP, permission rules,
    sandboxing, and enterprise controls define the "normal setup" boundary
    used for primary fit scoring.

## Quality notes

- BLS/O*NET wages are national medians across all industries; technology
  and streaming companies often pay above these medians, making the
  salary-equivalent values conservative for tech roles.
- Time allocation is bullet-proportional (documented limitation), not a
  measured time study.
- Scenario parameters are decision assumptions anchored to sources 5–8;
  they are editable constants in `scripts/02_build_value_model.py`.
