# Data Collection Project

This repository contains a system designed to  evaluate annotators for a data labeling tasks, source SEC filings and build prompts for a data labeling and QC workflow.

## What's here
- **screener-test/** – A short entry test. `grade.py` scores MCQs, validates citation fields, and simulates an LLM judge for the written response.
- **qualification-test/** – A longer follow-up test. `grade.py` auto-grades MCQs, checks citations, and emits JSON/JSONL reports for downstream LLM judging.
- **data-collection/** – Scripts and configs that download 10-K/10-Q filings, chunk them, draft prompts, and assign work to labelers. See `data-collection/docs/pipeline.md` for step-by-step commands.
- **data-collection/docs/** & **data-collection/data/** – Living documentation and generated artifacts (filings, chunks, prompts, allocation plans).
- - **qa/** – System prompts plus reviewer and SME guides that define how answers are checked for factual accuracy and citation quality.

## Run the graders
Both tests expect structured submissions and write machine-readable results.

```bash
# Screener (JSONL in, JSONL out)
python screener-test/grade.py submissions.jsonl results.jsonl

# Qualification (CSV in, JSON/JSONL out)
python qualification-test/grade.py
```

The screener script scores the provided JSONL file and writes one JSON result per line. The qualification script looks for `advanced_responses.csv` in the working directory and produces `grading_report.json` plus `judge_payload.jsonl`. See each directory for sample schemas and prompts.

## Data pipeline quickstart
1. `python data-collection/scripts/fetch_filings.py --count 40 --start-date 2023-10-01`
2. `python data-collection/scripts/index_filings.py data-collection/data/filings/filings.jsonl`
3. `python data-collection/scripts/generate_prompts.py --chunk-file data-collection/data/docs/chunks.jsonl --output data-collection/data/prompts/prompts.jsonl`
4. `python data-collection/scripts/allocate_labelers.py --prompts data-collection/data/prompts/prompts.jsonl --out data-collection/data/allocations/plan.json`

Set the required API keys, SEC `User-Agent`, and install `wkhtmltopdf` before running the scripts.

## Need to know
- Generated artifacts live under `data-collection/data/` and are safe to regenerate.
- Reviewer guidance and SME escalation rules live under `qa/`.
- Pass thresholds and grading logic are documented in `screener-test/methodology.md`, the test `questions.md`, and `answer_key.md` files.
