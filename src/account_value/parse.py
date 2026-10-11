"""Posting text parsing: HTML -> sections -> verbatim responsibility bullets.

Ported from the golden Crunchyroll parser (01_parse_postings.py) with the
company-specific phrases generalized out.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RESP_HEADING_PAT = re.compile(
    r"(responsibilit|responsabilit|duties|what you( will|.?ll) (do|be doing|accomplish)|"
    r"your (role|responsibilities|mission)|about (the|your|this) (role|job|position)|the role|"
    r"key responsibilities|day.?to.?day|in this role|areas of responsibility|"
    r"role overview|^the opportunity$|^what your contributions|"
    r"key areas of focus|^how you.?ll|^you will\b|you will$|"
    r"^main activities|^the work!? ?$|^success in your first|"
    r"^what your team does|^a day in the life|"
    r"purpose of the (job|role|position)|o seu desafio|sobre a vaga|担当業務|職務内容)",
    re.I,
)
STOP_HEADING_PAT = re.compile(
    r"^(what (we.?re looking for|you( will|.?ll) (need|bring)|we look for|makes|success)|"
    r"qualification|requirements?|"
    r"(basic|minimum) (qualification|requirement)s?|"
    r"who you are|you (are|have)|about you|nice to have|bonus points|skills|"
    r"experience|education|skills & competencies|working conditions|"
    r"about (us|the team|the opportunity|the company)|about the team|"
    r"our (mission|values|benefits)|compensation|pay|benefits|perks|culture|hybrid model|"
    r"why (join|you( will|.?ll) love)|what you.?ll love|let.?s talk about you|"
    r".*perks|knowledge\b|exigences|salary range|technical expertise|"
    r"additional capabilities|o que buscamos|we.?re excited about you|"
    r"eoe|equal|total rewards|how to apply|"
    r"future growth|応募資格|deployment.*|our commitment)",
    re.I,
)


def html_to_text(raw: str) -> str:
    text = html.unescape(raw)
    text = re.sub(r"<h[1-6][^>]*>", "\n@@H@@ ", text, flags=re.I)
    text = re.sub(r"</h[1-6]>", "\n", text, flags=re.I)
    text = re.sub(r"<(li|p|div|br|tr)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)  # second pass for double-escaped entities
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def extract_bullets(text: str) -> list[tuple[str, str]]:
    """Return (section, bullet_text) under responsibility-like headings."""
    out, section, in_resp = [], "", False
    lines = text.split("\n")
    for line in lines:
        m = re.match(r"^@@H@@\s*(.*)$", line)
        virtual = False
        if m:
            heading = m.group(1).strip().rstrip(":").strip()
        else:
            virtual = (len(line) < 70 and not line.endswith((".", "!", "?", ";"))
                       and (RESP_HEADING_PAT.search(line) or STOP_HEADING_PAT.match(line)))
            heading = line.strip().rstrip(":").strip()
            if not virtual:
                heading = None
        if heading is not None:
            if STOP_HEADING_PAT.match(heading):
                in_resp = False
                continue
            if RESP_HEADING_PAT.search(heading):
                section, in_resp = heading, True
            elif in_resp and not virtual:
                section = heading
            continue
        if not in_resp or not line:
            continue
        clean = re.sub(r"^[\-\u2022\*\u25cf\u25aa\u00b7\d{1,2}[\].)]\s*", "", line).strip()
        if 25 < len(clean) < 600 and not clean.endswith("?"):
            out.append((section, clean))
    if out:
        return out
    # Fallback: sentences from prose paragraphs under responsibility sections.
    out2, section, in_resp = [], "", False
    for line in lines:
        m = re.match(r"^@@H@@\s*(.*)$", line)
        virtual = False
        if m:
            heading = m.group(1).strip().rstrip(":").strip()
        else:
            virtual = (len(line) < 70 and not line.endswith((".", "!", "?", ";"))
                       and (RESP_HEADING_PAT.search(line) or STOP_HEADING_PAT.match(line)))
            heading = line.strip().rstrip(":").strip() if virtual else None
        if heading is not None:
            if STOP_HEADING_PAT.match(heading):
                in_resp = False
                continue
            if RESP_HEADING_PAT.search(heading):
                section, in_resp = heading, True
            continue
        if not in_resp or not line:
            continue
        for sent in re.split(r"(?<=[.;!])\s+", line):
            sent = sent.strip()
            if 40 < len(sent) < 600:
                out2.append((section, sent))
    return out2


@dataclass(frozen=True)
class PostedPay:
    """A posted pay range in US dollars, with how it was read."""
    min_usd: int = 0
    max_usd: int = 0
    mid_usd: int = 0
    note: str = ""  # "html block" | "text" | "text, CAD at 0.702 USD (…)" | "text, monthly ×12"

    def __bool__(self) -> bool:
        return self.mid_usd > 0


_CUR = r"(?:US\$|CA\$|C\$|A\$|\$|£|€|USD|CAD|GBP|EUR|AUD)"
_NUM = r"\d{1,3}(?:\s?,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"  # tolerates "$175 ,000"
_PER = r"(?:\s?(?:/|per\s)\s?(?:year|yr|annum|hour|hr|month))?"  # "$X/year up to $Y/year"
PAY_RANGE_PAT = re.compile(
    rf"(?P<c1>{_CUR})?\s?(?P<n1>{_NUM})\s?(?P<k1>[kK])?{_PER}\.?\s*(?:-|–|—|to|up to|and|through)\s*"
    rf"(?P<c2>{_CUR})?\s?(?P<n2>{_NUM})\s?(?P<k2>[kK])?(?:\s?(?P<c3>USD|CAD|GBP|EUR|AUD)\b)?"
)
PAY_SINGLE_PAT = re.compile(
    rf"(?P<c1>US\$|CA\$|C\$|A\$|\$|£|€)\s?(?P<n1>{_NUM})\s?(?P<k1>[kK])?(?:\s?(?P<c3>USD|CAD|GBP|EUR|AUD)\b)?"
)
# A line has to be about pay, and not about the business the hire will run.
PAY_CONTEXT_PAT = re.compile(r"salar|compensation|\bpay\b|\bbase\b|\bband\b|\brange\b|\bOTE\b|wage", re.I)
PAY_EXCLUDE_PAT = re.compile(
    r"\bACV\b|\bARR\b|revenue|quota|\bdeals?\b|budget|funding|valuation|customers|"
    r"\bloans?\b|portfolio|pipeline|bonus of", re.I)
PERIOD_HOUR = re.compile(r"per hour|/\s?h(ou)?r\b|hourly|an hour", re.I)
PERIOD_MONTH = re.compile(r"per month|/\s?month|monthly|a month", re.I)
_SYMBOL_CODE = {"US$": "USD", "$": "USD", "CA$": "CAD", "C$": "CAD", "A$": "AUD", "£": "GBP", "€": "EUR"}
PAY_MIN_ANNUAL_USD, PAY_MAX_ANNUAL_USD = 20_000, 1_000_000


@lru_cache(maxsize=1)
def fx_rates() -> tuple[dict[str, float], str]:
    """(usd_per_unit by currency code, label) from registry/fx_rates.yaml."""
    import yaml

    for candidate in (Path("registry/fx_rates.yaml"),
                      Path(__file__).resolve().parents[2] / "registry" / "fx_rates.yaml"):
        if candidate.exists():
            payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            return ({k.upper(): float(v) for k, v in (payload.get("usd_per_unit") or {}).items()},
                    f"{payload.get('source', 'fx_rates.yaml')}")
    return {"USD": 1.0}, "no fx_rates.yaml found"


def _amount(num: str, k: str | None, other_has_k: bool) -> float:
    value = float(num.replace(",", "").replace(" ", ""))
    if k or (other_has_k and value < 1000):
        value *= 1000
    return value


def _currency(*tokens: str | None) -> str:
    for token in tokens:
        if token:
            return _SYMBOL_CODE.get(token, token.upper())
    return "USD"


def _annualize(low: float, high: float, line: str) -> tuple[float, float, str]:
    if PERIOD_HOUR.search(line):
        return low * 2080, high * 2080, "hourly ×2080"
    if PERIOD_MONTH.search(line):
        return low * 12, high * 12, "monthly ×12"
    return low, high, ""


def _to_usd(low: float, high: float, currency: str, notes: list[str]) -> tuple[int, int] | None:
    rates, label = fx_rates()
    if currency not in rates:
        return None
    if currency != "USD":
        notes.append(f"{currency} at {rates[currency]:.3f} USD ({label})")
    low_usd, high_usd = round(low * rates[currency]), round(high * rates[currency])
    if low_usd > high_usd:
        low_usd, high_usd = high_usd, low_usd
    if not (PAY_MIN_ANNUAL_USD <= low_usd and high_usd <= PAY_MAX_ANNUAL_USD):
        return None
    return low_usd, high_usd


def _posted_pay_from_text(text: str) -> PostedPay:
    single_fallback: PostedPay | None = None
    for line in text.split("\n"):
        if len(line) > 1500 or PAY_EXCLUDE_PAT.search(line):
            continue
        has_context = bool(PAY_CONTEXT_PAT.search(line))
        for m in PAY_RANGE_PAT.finditer(line):
            if not (m.group("c1") or m.group("c2") or m.group("c3")):
                continue  # "3-5 years", "2-3 days": no currency anywhere
            if not has_context and not (m.group("c1") and m.group("c2")) and not (
                    m.group("c1") and "," in m.group("n1") and "," in m.group("n2")):
                continue  # without a pay word, only "$X - $Y" or "$X,XXX-Y,YYY" counts


            low = _amount(m.group("n1"), m.group("k1"), bool(m.group("k2")))
            high = _amount(m.group("n2"), m.group("k2"), bool(m.group("k1")))
            low, high, period = _annualize(low, high, line)
            notes = ["text"] + ([period] if period else [])
            usd = _to_usd(low, high, _currency(m.group("c3"), m.group("c1"), m.group("c2")), notes)
            if usd:
                return PostedPay(usd[0], usd[1], round(sum(usd) / 2), ", ".join(notes))
        if single_fallback is None:
            m = PAY_SINGLE_PAT.search(line)
            if m and re.search(r"salar|base|compensation", line, re.I):
                value = _amount(m.group("n1"), m.group("k1"), False)
                low, high, period = _annualize(value, value, line)
                notes = ["text, single figure"] + ([period] if period else [])
                usd = _to_usd(low, high, _currency(m.group("c3"), m.group("c1")), notes)
                if usd:
                    single_fallback = PostedPay(usd[0], usd[1], usd[0], ", ".join(notes))
    return single_fallback or PostedPay()


def extract_posted_pay_detail(raw_html: str) -> PostedPay:
    """Posted pay in USD: Greenhouse's pay-range HTML block first, then the
    posting text in any of the formats seen across Greenhouse, Lever, Ashby and
    Workday boards (ranges with symbols or codes, K suffixes, 'to'/'and'
    separators, monthly or hourly figures). Non-USD is converted at the dated
    rates in registry/fx_rates.yaml and the note says so."""
    text = html.unescape(raw_html)
    amounts = [int(a.replace(",", "")) for a in re.findall(
        r"pay-range[^>]*>(?:\s*<[^>]+>)*\s*\$\s?([\d,]{5,})", text)]
    if amounts:
        return PostedPay(min(amounts), max(amounts), round((min(amounts) + max(amounts)) / 2), "html block")
    # Greenhouse serves some boards entity-escaped (&lt;p&gt;…), so test for
    # tags on the unescaped text, not the raw payload.
    plain = html_to_text(text) if "<" in text else text
    return _posted_pay_from_text(plain)


def extract_posted_pay(raw_html: str) -> tuple[int, int, int]:
    """(min, max, mid) in USD, zeros if absent. See extract_posted_pay_detail."""
    pay = extract_posted_pay_detail(raw_html)
    return pay.min_usd, pay.max_usd, pay.mid_usd
