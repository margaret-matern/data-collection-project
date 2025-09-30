# Pipeline Overview

This document describes how to execute the end-to-end pipeline. Each stage writes structured outputs under `data/` and can be re-run independently.

## 1. Acquire Filings

Run `python scripts/fetch_filings.py --count 40 --start-date 2023-10-01` to download the 10-K/10-Q corpus. The script will:

1. Query the SEC search API for the most recent filings after the start date.
2. Resolve canonical document links and metadata.
3. Export the "Open as HTML" rendition as PDF via wkhtmltopdf/pdfkit.
4. Persist metadata in `data/filings/filings.jsonl` and PDFs under `data/filings/pdfs/`.

> **Note**: You must supply a valid `User-Agent` header (see script arguments) and have `wkhtmltopdf` installed locally for PDF creation.

## 2. Index and Chunk

Run `python scripts/index_filings.py data/filings/filings.jsonl` to extract text, identify section headers, attach page numbers, and create ~1–2k token chunks. Outputs:

- Page-level text in `data/docs/pages.jsonl`.
- Chunked segments in `data/docs/chunks.jsonl` with metadata `doc_id`, `page_span`, and `section_hint`.

## 3. Prompt Generation

Run `python scripts/generate_prompts.py --chunk-file data/docs/chunks.jsonl --output data/prompts/prompts.jsonl`. Export your OpenAI API key as `OPENAI_API_KEY` before running so the script can call the chat completions endpoint. The script enforces the mix:

- 30 prompts of type A.
- 50 prompts of type B.
- 45 prompts of type C (including 5 flagged as `C-Extended` leveraging more than 6 filings).

Outputs include metadata showing which filings were referenced.

## 4. Labeler Allocation

Finally, plan the labeling workload with `python scripts/allocate_labelers.py --prompts data/prompts/prompts.jsonl --out data/allocations/plan.json`. The allocator reads `config/labelers.yml` and `config/time_model.yml` to auto-distribute work across 12 labelers proportionally to their available hours while respecting skill focus.

Each script logs progress and writes idempotent artifacts so the repository serves as the single source of truth for the project.
