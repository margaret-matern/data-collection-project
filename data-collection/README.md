# Data Collection Pipeline

This directory houses the data collection assets required to curate, index, and distribute 10-K/10-Q filings dated on or after 2023-10-01. The workflow is broken into four major objectives:

1. **Acquire the 40 document corpus** complete with canonical EDGAR links, filing dates, and printable PDF renditions exported from the "Open as HTML" interface.
2. **Index the filings for grounded question generation** with page aware text, section hints, and ~1–2k token chunks.
3. **Generate the 130 prompts** in the A/B/C mix (A=30, B=50, C=45 with 5 of the C prompts flagged as extended).
4. **Persist artifacts and plan labeling operations** using a 12-person B/C labeling pool, declared availability, and per-item time models.

The subdirectories and scripts provide reproducible tooling for the entire workflow.
