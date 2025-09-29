# data-collection-project
Take home materials for data collection project


This repo contains a 5-question mini-test for single-document competency on SEC filings,
plus a grading script that auto-scores MCQs and uses an LLM-as-Judge for Q5.

## Run the grader
python grader/grade.py grader/schema_examples/submissions.jsonl grader/schema_examples/results.jsonl

See `docs/methodology.md` for pass criteria and rubric.

