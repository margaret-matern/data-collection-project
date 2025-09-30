cat > docs/methodology.md << 'EOF'
# Grading Methodology

Pass rule: total ≥ 5 points.
- Q1–Q4 (MCQs) = 1 point each (must match the key).
- Q5 (short answer) = 2 points if LLM-as-Judge returns:
  - factuality ≥ 5, citation ≥ 4, clarity ≥ 4 (safety is fixed at 5 for this task).

Pre-checks for Q5: percent-looking answer, quote ≤ 30 words, positive page number, sec.gov URL, section present.

Use evidence-only judging. See `mini_test/judge_prompt.md`.
EOF
