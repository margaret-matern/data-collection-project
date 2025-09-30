#!/usr/bin/env python3
"""Extract page-level text from PDFs and build chunked documents."""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import pdfplumber
import tiktoken

SECTION_REGEX = re.compile(r"^(item\s+\d+[a-z]?)(?:\.|:)?\s*(.*)$", re.IGNORECASE)
DEFAULT_MODEL = "gpt-3.5-turbo"


def read_filings(metadata_path: Path) -> List[dict]:
    filings = []
    with metadata_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            filings.append(json.loads(line))
    return filings


def detect_section(line: str) -> Optional[str]:
    match = SECTION_REGEX.match(line.strip())
    if match:
        label = match.group(1).upper().replace(" ", "")
        suffix = match.group(2).strip()
        return f"{label} {suffix}".strip()
    return None


def page_sections(text: str) -> List[str]:
    sections = []
    for line in text.splitlines():
        section = detect_section(line)
        if section:
            sections.append(section)
    return sections


def chunk_text(text: str, encoder, target_tokens: int = 1500, window_tokens: int = 2000) -> List[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buffer: List[str] = []
    token_count = 0
    for para in paragraphs:
        para_tokens = len(encoder.encode(para))
        if token_count + para_tokens > window_tokens and buffer:
            chunks.append("\n\n".join(buffer))
            buffer = [para]
            token_count = para_tokens
        else:
            buffer.append(para)
            token_count += para_tokens
        if token_count >= target_tokens:
            chunks.append("\n\n".join(buffer))
            buffer = []
            token_count = 0
    if buffer:
        chunks.append("\n\n".join(buffer))
    return chunks


def derive_section_hint(sections: List[str]) -> Optional[str]:
    priority = [
        "ITEM1A",
        "ITEM7",
        "ITEM7A",
        "ITEM2",
        "ITEM8",
        "ITEM9",
        "ITEM1",
    ]
    for candidate in priority:
        for section in sections:
            if section.upper().startswith(candidate):
                return section
    return sections[0] if sections else None


def process_pdf(doc: dict, encoder, base_path: Path) -> Tuple[List[dict], List[dict]]:
    pdf_path = base_path / doc["pdf_path"]
    pages_output: List[dict] = []
    chunks_output: List[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        sections_per_page: List[List[str]] = []
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            sections = page_sections(text)
            sections_per_page.append(sections)
            pages_output.append(
                {
                    "doc_id": doc["doc_id"],
                    "page": page_number,
                    "text": text,
                    "sections": sections,
                }
            )
    # Chunking with awareness of section hints and pages
    current_chunk: List[str] = []
    current_pages: List[int] = []
    current_sections: List[str] = []

    def flush_chunk():
        if not current_chunk:
            return
        chunk_text_value = "\n".join(current_chunk)
        chunk_sections = derive_section_hint(current_sections)
        chunks_output.append(
            {
                "doc_id": doc["doc_id"],
                "page_start": current_pages[0],
                "page_end": current_pages[-1],
                "section_hint": chunk_sections,
                "text": chunk_text_value,
            }
        )
        current_chunk.clear()
        current_pages.clear()
        current_sections.clear()

    for page_record in pages_output:
        page_text = page_record["text"]
        if not page_text:
            continue
        page_chunks = chunk_text(page_text, encoder)
        for chunk in page_chunks:
            tokens = len(encoder.encode(chunk))
            if tokens > 2000:
                logging.warning("Chunk exceeds 2000 tokens on doc %s page %s", doc["doc_id"], page_record["page"])
            current_chunk.append(chunk)
            current_pages.append(page_record["page"])
            current_sections.extend(page_record.get("sections", []))
            combined_tokens = len(encoder.encode("\n".join(current_chunk)))
            if combined_tokens >= 1800:
                flush_chunk()
        if current_chunk:
            flush_chunk()

    return pages_output, chunks_output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path, help="Path to filings metadata JSONL")
    parser.add_argument("--pages-out", type=Path, default=Path("data/docs/pages.jsonl"))
    parser.add_argument("--chunks-out", type=Path, default=Path("data/docs/chunks.jsonl"))
    parser.add_argument("--pdf-root", type=Path, default=Path("."))
    parser.add_argument("--encoding", type=str, default=DEFAULT_MODEL)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    filings = read_filings(args.metadata)
    encoder = tiktoken.encoding_for_model(args.encoding)

    args.pages_out.parent.mkdir(parents=True, exist_ok=True)
    args.chunks_out.parent.mkdir(parents=True, exist_ok=True)

    with args.pages_out.open("w", encoding="utf-8") as pages_file, args.chunks_out.open(
        "w", encoding="utf-8"
    ) as chunks_file:
        for doc in filings:
            logging.info("Indexing %s", doc["doc_id"])
            pages, chunks = process_pdf(doc, encoder, args.pdf_root)
            for page_record in pages:
                pages_file.write(json.dumps(page_record) + "\n")
            for chunk_record in chunks:
                chunks_file.write(json.dumps(chunk_record) + "\n")

    logging.info("Indexing complete")


if __name__ == "__main__":
    main()
