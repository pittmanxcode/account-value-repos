"""Collector registry: ATS name -> collect()."""

from __future__ import annotations

from pathlib import Path

from account_value.collectors import ashby, greenhouse, jsonld, lever, workday
from account_value.collectors.base import (
    CollectionResult as CollectionResult,
)
from account_value.collectors.base import (
    CollectorError as CollectorError,
)
from account_value.collectors.base import (
    TermsBlocked as TermsBlocked,
)
from account_value.collectors.base import (
    UnsupportedCollector as UnsupportedCollector,
)


def collect(ats: str, token_or_url: str, raw_dir: Path, fetch=None) -> CollectionResult:
    if ats == "greenhouse":
        return greenhouse.collect(token_or_url, raw_dir, fetch=fetch)
    if ats == "lever":
        return lever.collect(token_or_url, raw_dir, fetch=fetch)
    if ats == "ashby":
        return ashby.collect(token_or_url, raw_dir, fetch=fetch)
    if ats == "workday":
        workday.collect(token_or_url, raw_dir, fetch=fetch)
        raise UnsupportedCollector("workday collector never returns")  # pragma: no cover
    if ats == "jsonld":
        return jsonld.collect(token_or_url, raw_dir, fetch=fetch)
    raise UnsupportedCollector(f"unsupported ATS: {ats!r}")
