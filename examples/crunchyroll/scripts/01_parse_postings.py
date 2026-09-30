#!/usr/bin/env python3
"""Parse the raw Greenhouse board snapshot into jobs.csv and responsibilities.csv.

Reads:  data/raw/greenhouse_board_snapshot.json
Writes: data/processed/jobs.csv
        data/processed/responsibilities.csv  (verbatim responsibility bullets)
"""
import csv
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "greenhouse_board_snapshot.json"
OUT_JOBS = ROOT / "data" / "processed" / "jobs.csv"
OUT_RESP = ROOT / "data" / "processed" / "responsibilities.csv"

# Section headers that typically contain responsibilities in Crunchyroll postings.
RESP_HEADING_PAT = re.compile(
    r"(responsibilit|duties|what you.?ll (do|be doing)|what you will (do|be doing)|"
    r"your (role|responsibilities)|about (the|your) (role|job|position)|the role|"
    r"key responsibilities|day.?to.?day|in this role|areas of responsibility|"
    r"role overview|担当業務|職務内容)",
    re.I,
)
STOP_HEADING_PAT = re.compile(
    r"^(what (we.?re looking for|you.?ll need|we look for|makes|success)|qualification|"
    r"requirements|who you are|you (are|have)|about you|nice to have|bonus points|skills|"
    r"experience|education|skills & competencies|working conditions|"
    r"about (us|crunchyroll|the team|the opportunity)|about the team|"
    r"our (mission|values|benefits)|compensation|pay|benefits|perks|"
    r"why (join|crunchyroll|you will love)|eoe|equal|total rewards|how to apply|"
    r"future growth|応募資格|クランチロールで働く魅力とは|deployment.*|our commitment)",
    re.I,
)


def html_to_text(raw: str) -> str:
    text = html.unescape(raw)
    # Mark headings and list items before stripping tags.
    text = re.sub(r"<h[1-6][^>]*>", "\n@@H@@ ", text, flags=re.I)
    text = re.sub(r"</h[1-6]>", "\n", text, flags=re.I)
    text = re.sub(r"<(li|p|div|br|tr)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)  # second pass for double-escaped entities
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def extract_bullets(text: str):
    """Return list of (section, bullet_text) under responsibility-like headings.

    Once inside a responsibilities section, sub-headings do not stop collection;
    only a STOP_HEADING_PAT match does. Falls back to sentence capture when a
    section has no list-style bullets.
    """
    out, section, in_resp = [], "", False
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        m = re.match(r"^@@H@@\s*(.*)$", line)
        virtual = False
        if m:
            heading = m.group(1).strip().rstrip(":").strip()
        else:
            # Some postings style section headers as plain short lines.
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
                section = heading  # sub-heading within the duties section
            continue
        if not in_resp or not line:
            continue
        clean = re.sub(r"^[\-\u2022\*\u25cf\u25aa\u00b7\d{1,2}[\].)]\s*", "", line).strip()
        if 25 < len(clean) < 600 and not clean.endswith("?"):
            out.append((section, clean))
    if out:
        return out
    # Fallback: split prose paragraphs under responsibility sections into sentences.
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


def main() -> int:
    data = json.loads(RAW.read_text(encoding="utf-8"))
    jobs, resp_rows = [], []
    for j in data["jobs"]:
        jid = j["id"]
        dept = "; ".join(d["name"] for d in j.get("departments", []))
        office = "; ".join(o["name"] for o in j.get("offices", []))
        text = html_to_text(j.get("content") or "")
        pay_min = pay_max = pay_mid = ""
        # Structured pay ranges (Greenhouse pay-range blocks, typically US).
        raw_html = html.unescape(j.get("content") or "")
        amounts = [int(a.replace(",", "")) for a in re.findall(
            r'pay-range[^>]*>(?:\s*<[^>]+>)*\s*\$\s?([\d,]{5,})', raw_html)]
        pay_min = min(amounts) if amounts else ""
        pay_max = max(amounts) if amounts else ""
        pay_mid = round((min(amounts) + max(amounts)) / 2) if amounts else ""
        jobs.append({
            "job_id": jid,
            "title": j["title"].strip(),
            "department": dept,
            "office": office,
            "location": j["location"]["name"],
            "language": j.get("language", ""),
            "first_published": (j.get("first_published") or "")[:10],
            "updated_at": (j.get("updated_at") or "")[:10],
            "requisition_id": j.get("requisition_id") or "",
            "pay_min_posted": pay_min,
            "pay_max_posted": pay_max,
            "pay_mid_posted": pay_mid,
            "url": j["absolute_url"],
            "content_chars": len(text),
        })
        for i, (section, bullet) in enumerate(extract_bullets(text), 1):
            resp_rows.append({
                "job_id": jid,
                "title": j["title"].strip(),
                "department": dept,
                "resp_seq": i,
                "section": section,
                "verbatim_responsibility": bullet,
            })

    with OUT_JOBS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(jobs[0].keys()))
        w.writeheader()
        w.writerows(jobs)
    with OUT_RESP.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(resp_rows[0].keys()))
        w.writeheader()
        w.writerows(resp_rows)

    print(f"jobs: {len(jobs)} -> {OUT_JOBS}")
    print(f"responsibility bullets: {len(resp_rows)} -> {OUT_RESP}")
    thin = [j["title"] for j in jobs if not any(r["job_id"] == j["job_id"] for r in resp_rows)]
    print(f"postings with 0 bullets extracted ({len(thin)}): {thin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
