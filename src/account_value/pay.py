"""Compensation basis (US-equivalent per the golden-build decision).

Precedence, per the methodology:
1. Posted US pay range captured by the collector (pay_mid_posted).
2. Per-account title overrides (exact title -> SOC + seniority).
3. Heuristic title -> SOC + seniority keyword mapping.
Every row records its pay_source; BLS OEWS May 2025 medians ship with the
package via O*NET (data/soc_wages_2025.txt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

WAGE_DATA = "soc_wages_2025.txt"
ANNUAL_HOURS = 1920
LOADED_FACTOR = 1.30

LEVELS = {
    "entry": 0.80, "mid": 0.90, "senior": 1.10, "lead": 1.25,
    "staff": 1.50, "manager": 1.35, "director": 1.60, "exec": 2.00,
}

OCC_LABELS = {
    "11-1021.00": "General and Operations Managers",
    "11-2021.00": "Marketing Managers",
    "11-3013.00": "Facilities Managers",
    "11-3021.00": "Computer and Information Systems Managers",
    "11-3031.00": "Financial Managers",
    "11-3061.00": "Purchasing Managers",
    "11-3121.00": "Human Resources Managers",
    "13-1082.00": "Project Management Specialists",
    "13-1111.00": "Management Analysts",
    "13-1151.00": "Training and Development Specialists",
    "13-1161.00": "Market Research Analysts",
    "13-2011.00": "Accountants and Auditors",
    "13-2051.00": "Financial and Investment Analysts",
    "15-1212.00": "Information Security Analysts",
    "15-1243.00": "Database Architects and Engineers",
    "15-1244.00": "Network and Computer Systems Administrators",
    "15-1252.00": "Software Developers",
    "15-2051.00": "Data Scientists",
    "23-1011.00": "Lawyers",
    "27-1011.00": "Art Directors",
    "27-1024.00": "Graphic Designers",
    "27-2012.00": "Producers and Directors",
    "27-3031.00": "Public Relations Specialists",
    "27-3043.00": "Editors",
    "43-3031.00": "Bookkeeping and Accounting Clerks",
    "43-4051.00": "Customer Service Representatives",
    "43-6014.00": "Secretaries and Administrative Assistants",
}

# Heuristic title -> SOC keyword mapping (checked in order).
_HEURISTIC = [
    (r"data (engineer|engineering)|data pipeline|analytics engineer", "15-1252.00"),
    (r"data (scientist|science)|machine learning|mlops|\bai\b (engineer|architect)", "15-2051.00"),
    (r"database|\bdba\b", "15-1243.00"),
    (r"security|appsec|identity", "15-1212.00"),
    (r"sre|site reliability|systems? (administrator|engineer)|it engineer|salesforce (technical )?admin", "15-1244.00"),
    (r"software|engineer|developer|full.?stack|frontend|backend|architect", "15-1252.00"),
    (r"tax|sox|account|accounting|accounts payable", "13-2011.00"),
    (r"financial|finance|fp&a|deal management", "13-2051.00"),
    (r"instructional|training|enablement", "13-1151.00"),
    (r"cx|customer (experience|support)|insights", "13-1161.00"),
    (r"program manage|project manage|technical program", "13-1082.00"),
    (r"strategy|strategic|business affairs|metadata|distribution", "13-1111.00"),
    (r" sourcing|procurement", "11-3061.00"),
    (r"people|human resources|\bhr\b", "11-3121.00"),
    (r"counsel|legal|anti-?piracy", "23-1011.00"),
    (r"producer|co-?production", "27-2012.00"),
    (r"designer|design|creative", "27-1024.00"),
    (r"marketing|gtm|communications", "11-2021.00"),
    (r"general manager|\bvp\b|vice president|chief", "11-1021.00"),
]

_SENIORITY = [
    (r"\bintern\b|\bassociate i\b|\bi\b|entry", "entry"),
    (r"\bstaff\b|principal", "staff"),
    (r"\blead\b", "lead"),
    (r"director", "director"),
    (r"vice president|\bvp\b|president|general manager|chief|executive", "exec"),
    (r"manager|senior manager", "manager"),
    (r"senior|sr\.?|\bii{1,3}\b|\biii\b", "senior"),
]


def _load_wages() -> dict[str, int]:
    wages: dict[str, int] = {}
    text = resources.files("account_value").joinpath(f"data/{WAGE_DATA}").read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"([\d.-]+) :: .*?([\d,]+) annual", line)
        if m:
            wages[m.group(1)] = int(m.group(2).replace(",", ""))
    wages.setdefault("15-1252.00", 135980)  # harvested in the original probe
    return wages


OCC_WAGE = _load_wages()


@dataclass(frozen=True)
class PayBasis:
    soc: str
    occupation: str
    seniority: str
    base_pay: int
    pay_source: str
    hourly: float
    loaded_hourly: float


def _detect_seniority(title: str) -> str:
    lowered = title.lower()
    for pattern, level in _SENIORITY:
        if re.search(pattern, lowered):
            return level
    return "mid"


def _heuristic_soc(title: str) -> str:
    lowered = title.lower()
    for pattern, soc in _HEURISTIC:
        if re.search(pattern, lowered):
            return soc
    return "13-1111.00"  # management analysts: the honest generic fallback


def pay_basis(
    title: str,
    posted_mid: int | str | None = None,
    overrides: dict[str, tuple[str, str]] | None = None,
    posted_note: str = "",
) -> PayBasis:
    """Resolve the pay basis for one title.

    overrides maps exact titles -> (soc, seniority), loaded from a per-account
    YAML file when one exists. posted_note says how a posted range was read
    (see parse.PostedPay) and is carried into pay_source.
    """
    if posted_mid:
        base = int(posted_mid)
        soc, seniority = "", ""
        source = f"posted pay range ({posted_note})" if posted_note else "posted pay range"
        if overrides and title in overrides:
            soc, seniority = overrides[title]
        else:
            soc, seniority = _heuristic_soc(title), _detect_seniority(title)
    elif overrides and title in overrides:
        soc, seniority = overrides[title]
        base = round(OCC_WAGE[soc] * LEVELS[seniority])
        source = "BLS OEWS May 2025 median × seniority factor"
    else:
        soc, seniority = _heuristic_soc(title), _detect_seniority(title)
        base = round(OCC_WAGE[soc] * LEVELS[seniority])
        source = "BLS OEWS May 2025 median × seniority factor (heuristic title match)"
    return PayBasis(
        soc=soc,
        occupation=OCC_LABELS.get(soc, "unknown occupation"),
        seniority=seniority,
        base_pay=base,
        pay_source=source,
        hourly=round(base / ANNUAL_HOURS, 2),
        loaded_hourly=round(base / ANNUAL_HOURS * LOADED_FACTOR, 2),
    )


def load_title_overrides(path: Path) -> dict[str, tuple[str, str]]:
    """Load a per-account title map YAML ({title: {soc: ..., seniority: ...}})."""
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {str(k): (v["soc"], v["seniority"]) for k, v in raw.items()}
