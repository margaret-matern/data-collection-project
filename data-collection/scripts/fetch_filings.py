#!/usr/bin/env python3
"""Download a corpus of 10-K/10-Q filings and export printable PDFs."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pdfkit
import requests
from dateutil import parser as dateparser

SEARCH_ENDPOINT = "https://efts.sec.gov/LATEST/search-index"
USER_AGENT_FALLBACK = "FilingsCollector/1.0 contact@example.com"


@dataclass
class Filing:
    doc_id: str
    cik: str
    accession_no: str
    company: str
    form_type: str
    filed_at: str
    filing_url: str
    html_url: str
    pdf_path: Optional[str] = None

    @property
    def canonical_url(self) -> str:
        return self.filing_url


def build_search_payload(start_date: str, from_offset: int, page_size: int) -> dict:
    return {
        "keys": "formType:\"10-K\" OR formType:\"10-Q\"",
        "category": "custom",
        "forms": ["10-K", "10-Q"],
        "startdt": start_date,
        "from": from_offset,
        "size": page_size,
        "sortField": "filedAt",
        "sortOrder": "desc",
    }


def fetch_search_results(session: requests.Session, start_date: str, total: int, page_size: int = 100) -> Iterable[dict]:
    fetched = 0
    while fetched < total:
        payload = build_search_payload(start_date, fetched, page_size)
        logging.info("Querying SEC search API from offset %s", fetched)
        resp = session.post(SEARCH_ENDPOINT, json=payload)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break
        for hit in hits:
            source = hit.get("_source", {})
            yield source
            fetched += 1
            if fetched >= total:
                break
        time.sleep(0.2)


def to_filing(hit: dict) -> Optional[Filing]:
    accession = hit.get("adsh") or hit.get("accessionNumber")
    cik = hit.get("cik")
    filed_at = hit.get("filedAt") or hit.get("filed")
    html_url = hit.get("linkToHtml") or hit.get("linkToFilingDetails")
    filing_url = hit.get("linkToFilingDetails")
    if not (accession and cik and filed_at and filing_url and html_url):
        return None
    filed_date = dateparser.parse(filed_at).date().isoformat()
    doc_id = f"{cik}-{accession}".replace("/", "-")
    return Filing(
        doc_id=doc_id,
        cik=str(cik).lstrip("0"),
        accession_no=accession.replace("-", ""),
        company=hit.get("companyName", ""),
        form_type=hit.get("formType", ""),
        filed_at=filed_date,
        filing_url=filing_url,
        html_url=html_url,
    )


def ensure_pdf(html_content: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdfkit.from_string(html_content, str(output_path))


def download_filings(
    filings: Iterable[Filing],
    session: requests.Session,
    output_dir: Path,
    pdf_dir: Path,
    force: bool = False,
) -> List[Filing]:
    stored: List[Filing] = []
    for filing in filings:
        pdf_path = pdf_dir / f"{filing.doc_id}.pdf"
        if pdf_path.exists() and not force:
            logging.info("PDF already exists for %s", filing.doc_id)
            filing.pdf_path = str(pdf_path.relative_to(output_dir.parent))
            stored.append(filing)
            continue
        logging.info("Downloading HTML for %s", filing.doc_id)
        resp = session.get(filing.html_url)
        resp.raise_for_status()
        ensure_pdf(resp.text, pdf_path)
        filing.pdf_path = str(pdf_path.relative_to(output_dir.parent))
        stored.append(filing)
        time.sleep(0.3)
    return stored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=40, help="Number of filings to collect")
    parser.add_argument("--start-date", type=str, default="2023-10-01", help="Earliest filing date (YYYY-MM-DD)")
    parser.add_argument("--output", type=Path, default=Path("data/filings/filings.jsonl"), help="Metadata output path")
    parser.add_argument("--pdf-dir", type=Path, default=Path("data/filings/pdfs"), help="Directory to store PDFs")
    parser.add_argument("--user-agent", type=str, default=os.getenv("SEC_USER_AGENT", USER_AGENT_FALLBACK))
    parser.add_argument("--force", action="store_true", help="Re-download and overwrite existing PDFs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent, "Accept-Encoding": "gzip, deflate"})

    raw_hits = fetch_search_results(session, args.start_date, args.count)
    filings = []
    for hit in raw_hits:
        filing = to_filing(hit)
        if filing is None:
            continue
        filings.append(filing)
        if len(filings) >= args.count:
            break

    if len(filings) < args.count:
        logging.warning("Only located %s filings matching constraints", len(filings))

    stored = download_filings(filings, session, args.output, args.pdf_dir, force=args.force)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for filing in stored:
            record = asdict(filing)
            record["canonical_url"] = filing.canonical_url
            f.write(json.dumps(record) + "\n")

    logging.info("Wrote %s filings to %s", len(stored), args.output)


if __name__ == "__main__":
    main()
