"""Workday: no public unauthenticated posting API exists.

Per the honesty rule, this collector records terms_blocked/unsupported
rather than scraping the CaelumGraph session layer. A Workday account is a
failure record with 'where to look' guidance, eligible for backfill.
"""

from __future__ import annotations

from pathlib import Path

from account_value.collectors.base import TermsBlocked


def collect(token: str, raw_dir: Path, fetch=None) -> None:
    del token, raw_dir, fetch
    raise TermsBlocked(
        "workday has no public unauthenticated posting API; the board requires"
        " a browser session we do not automate — record 'unknown, where looked'"
        " (careers site, Workday tenant) and backfill from the next candidate"
    )
