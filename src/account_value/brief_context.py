"""Assemble the inputs for an account brief into one readable context file.

The brief itself is written by a reasoning-and-research pass (see
docs/ACCOUNT_BRIEF_METHOD.md and .claude/skills/account-brief). This module
only gathers what that pass needs from a finished package: the postings
verbatim, the pipeline's role numbers, and the figures the postings quote.
It computes nothing new and claims nothing.
"""

from __future__ import annotations

import csv
import json
import re
from html import escape as html_escape
from pathlib import Path

from account_value.parse import html_to_text

# Lines in a posting that carry a figure worth checking at source: a number
# with a unit, multiplier, or scale word next to it.
FIGURE_PATTERN = re.compile(
    r"\d[\d,.]*\s*(%|x\b|\+|k\b|mm?\b|b\b|bn\b|million|billion|thousand|"
    r"per (day|month|year|week)|/day|/month|/year|a day|a month|a year|"
    r"hours?|days?|weeks?|months?|years?|customers|clients|loans|users|"
    r"transactions|requests|jobs|events|engineers|teams)",
    re.I,
)
# Figure lines that are about the candidate or the package, not the business.
FIGURE_NOISE = re.compile(
    r"years? (of|in) |\d\+? ?years?[' ]* experience|travel|compensation|salary|401k|equity|"
    r"bonding|weeks off|paid|pto|holiday|benefit|direct reports|days per week",
    re.I,
)
# Mentions that place an account against the study sheet's entries.
TECH_PATTERN = re.compile(
    r"\b(python|java\b|kotlin|golang|rust|ruby|rails|node\.?js|typescript|react|"
    r"\.net|c#|c\+\+|scala|php|cobol|mainframe|kubernetes|k8s|docker|terraform|"
    r"aws|gcp|google cloud|azure|postgres|mysql|vitess|clickhouse|redis|kafka|"
    r"snowflake|databricks|spark|airflow|dbt|graphql|grpc|microservices?|monolith|"
    r"legacy|migration|modernization|on-?call|incident|sre|ci/cd|github|gitlab|"
    r"soc ?2|hipaa|pci|sox|fedramp|iso 27001|llm|machine learning)\b",
    re.I,
)
ENGINEERING_SOC_PREFIXES = ("15-",)  # computer and mathematical occupations


def _posting_texts(ats: str, payload) -> list[dict]:
    """Normalize one ATS snapshot into [{title, department, location, url,
    published, text}] with the posting body as plain text."""
    out = []
    if ats == "ashby":
        for p in payload.get("jobs", []):
            raw = p.get("descriptionHtml") or p.get("descriptionPlain") or ""
            out.append({
                "title": p.get("title", ""), "department": p.get("department", ""),
                "location": p.get("location", ""), "url": p.get("jobUrl", ""),
                "published": (p.get("publishedAt") or "")[:10],
                "text": html_to_text(raw),
            })
    elif ats in ("greenhouse", "jsonld"):
        for p in payload.get("jobs", []):
            out.append({
                "title": p.get("title", ""),
                "department": "; ".join(d["name"] for d in p.get("departments", [])),
                "location": (p.get("location") or {}).get("name", ""),
                "url": p.get("absolute_url", ""),
                "published": (p.get("first_published") or "")[:10],
                "text": html_to_text(p.get("content") or ""),
            })
    elif ats == "lever":
        for p in payload:
            raw = p.get("descriptionPlain", "") or p.get("description", "")
            for item in p.get("lists") or []:
                heading = html_escape((item.get("text") or "").strip())
                content = item.get("content") or ""
                if heading and content:
                    raw += f"\n<h3>{heading}</h3>\n{content}"
            if p.get("additionalPlain"):
                raw += "\n" + p["additionalPlain"]
            cats = p.get("categories", {})
            out.append({
                "title": p.get("text", ""), "department": cats.get("department", ""),
                "location": cats.get("location", ""),
                "url": p.get("hostedUrl", "") or p.get("applyUrl", ""),
                "published": str(p.get("createdAt", "")),
                "text": html_to_text(raw) if "<" in raw else raw,
            })
    elif ats == "workday":
        for p in payload.get("jobs", []):
            out.append({
                "title": p.get("title", ""), "department": "",
                "location": p.get("location", ""), "url": p.get("externalUrl", ""),
                "published": (p.get("startDate") or "")[:10],
                "text": html_to_text(p.get("jobDescription") or ""),
            })
    else:
        raise ValueError(f"no brief-context reader for ats {ats!r}")
    for p in out:
        p["text"] = p["text"].replace("@@H@@ ", "## ")
    return out


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build_context(package_dir: Path) -> str:
    package_dir = Path(package_dir)
    meta = json.loads((package_dir / "account-value.json").read_text(encoding="utf-8"))
    request, collection = meta["request"], meta["collection"]
    company = request["company_name"]
    ats = collection["ats"]
    snapshot = package_dir / "data" / "raw" / collection["snapshot"]
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    postings = _posting_texts(ats, payload)
    roles = _read_csv(package_dir / "data" / "processed" / "role_summary.csv")

    total_saved = sum(float(r["saved_hours_base"]) for r in roles)
    eng = [r for r in roles if r["occupation_soc"].startswith(ENGINEERING_SOC_PREFIXES)]
    eng_saved = sum(float(r["saved_hours_base"]) for r in eng)
    eng_value = sum(float(r["saved_value_base"]) for r in eng)

    lines = [
        f"# {company} — brief context",
        "",
        "Gathered by `account-value brief-context`. Everything here is either copied "
        "verbatim from the postings or taken from the pipeline's role numbers. "
        "Nothing is researched or inferred; that is the brief's job.",
        "",
        "## Account",
        f"- Company: {company} · domain: {request.get('domain') or 'unknown'}",
        f"- Postings: {len(postings)} via {ats} · snapshot {collection['snapshot']} "
        f"(sha256 {collection['snapshot_hash'][:12]}…) · generated {meta['generated_at'][:10]}",
        f"- Careers: {request.get('careers_url') or 'unknown'}",
        "",
        "## Pipeline numbers (open-req equivalents, base scenario)",
        f"- Saved hours, all {len(roles)} roles: {total_saved:,.0f} h/yr",
        f"- Saved hours, engineering roles only (SOC 15-xxxx, {len(eng)} roles): "
        f"{eng_saved:,.0f} h/yr · ${eng_value:,.0f}",
        "- Label for both: pipeline estimate; one FTE per open posting; categories built "
        "for another company. Use as a starting figure to check, never as a claim.",
        "",
        "## Roles",
        "",
        "| Title | Dept | SOC | US-equiv pay | Pay source | Saved h (base) |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(roles, key=lambda r: -float(r["saved_hours_base"])):
        lines.append(
            f"| {r['title']} | {r['department']} | {r['occupation_soc']} | "
            f"${float(r['us_equiv_base_pay']):,.0f} | {r['pay_source']} | "
            f"{float(r['saved_hours_base']):,.0f} |"
        )

    figures, techs = [], {}
    for p in postings:
        for ln in p["text"].split("\n"):
            if ln.startswith("## ") or len(ln) > 700:
                continue
            if (FIGURE_PATTERN.search(ln) and not FIGURE_NOISE.search(ln)
                    and not re.search(r"\$\s?\d", ln)):
                figures.append((p["title"], ln))
            for m in TECH_PATTERN.finditer(ln):
                techs.setdefault(m.group(0).lower(), set()).add(p["title"])
    seen, dedup = set(), []
    for title, ln in figures:
        if ln not in seen:
            seen.add(ln)
            dedup.append((title, ln))

    lines += ["", "## Figures quoted in postings (verbatim; check each at source)", ""]
    lines += [f"- [{t}] {ln}" for t, ln in dedup] or ["- none found"]
    lines += ["", "## Technology and practice mentions", ""]
    for key in sorted(techs, key=lambda k: (-len(techs[k]), k)):
        lines.append(f"- {key}: {len(techs[key])} posting(s) — {'; '.join(sorted(techs[key])[:4])}")
    if not techs:
        lines.append("- none found")

    lines += ["", "## Postings, verbatim", ""]
    for p in postings:
        lines += [
            f"### {p['title']}",
            f"{p['department']} · {p['location']} · published {p['published'] or 'unknown'} · {p['url']}",
            "",
            p["text"],
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def write_context(package_dir: Path) -> Path:
    out = Path(package_dir) / "brief-context.md"
    out.write_text(build_context(package_dir), encoding="utf-8")
    return out
