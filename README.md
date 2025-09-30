# Data Collection Project

This repository contains a system designed to  evaluate annotators for a data labeling tasks, source SEC filings and build prompts for a data labeling and QC workflow.

## What's here
- **screener-test/** – A short entry test. `grade.py` scores MCQs, validates citation fields, and simulates an LLM judge for the written response.
- **qualification-test/** – A longer follow-up test. `grade.py` auto-grades MCQs, checks citations, and emits JSON/JSONL reports for downstream LLM judging.
- **data-collection/** – Scripts and configs that download 10-K/10-Q filings, chunk them, draft prompts, and assign work to labelers. See `data-collection/docs/pipeline.md` for step-by-step commands.
- **data-collection/docs/** & **data-collection/data/** – Living documentation and generated artifacts (filings, chunks, prompts, allocation plans).
- **qa/** – System prompts plus reviewer and SME guides that define how answers are checked for factual accuracy and citation quality.

