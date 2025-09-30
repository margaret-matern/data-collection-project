"""Light-weight LLM triage heuristics for QA stage 2.

The real system uses an LLM prompt (see ``qa/llm-system-prompt``).  To keep the
repository runnable without external dependencies, we approximate the behavior
with a deterministic heuristic that checks whether salient phrases from the
answer appear in the cited quotes.  The output mirrors the production shape:
priority flag (``HIGH``/``LOW``) plus a short reason string.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List
import re


@dataclass
class TriageResult:
    priority: str
    reason: str


KEYWORD_RE = re.compile(r"[A-Za-z0-9%$,.]+")
PRIORITY_HIGH = "HIGH"
PRIORITY_LOW = "LOW"


def _extract_keywords(answer: str) -> List[str]:
    tokens = KEYWORD_RE.findall(answer or "")
    keywords: List[str] = []
    for token in tokens:
        if token.isdigit() and len(token) == 1:
            continue
        if len(token) <= 3 and not re.search(r"\d", token):
            continue
        keywords.append(token.lower())
    return keywords


def _quotes_from_citations(citations: Iterable[Dict]) -> List[str]:
    quotes: List[str] = []
    for citation in citations or []:
        quote = (citation or {}).get("quote")
        if quote:
            quotes.append(str(quote).lower())
    return quotes


def triage_submission(submission: Dict) -> TriageResult:
    """Assign a triage priority to a submission based on quote coverage."""

    answer = submission.get("answer", "") or ""
    citations = submission.get("citations", []) or []
    keywords = _extract_keywords(answer)
    quotes = _quotes_from_citations(citations)

    if not answer.strip():
        return TriageResult(PRIORITY_HIGH, "blank answer")
    if not quotes:
        return TriageResult(PRIORITY_HIGH, "no supporting quotes provided")

    missing: List[str] = []
    concatenated = " \n ".join(quotes)
    for keyword in keywords:
        if keyword not in concatenated:
            missing.append(keyword)
        if len(missing) >= 3:
            break

    if missing:
        reason = f"answer keywords missing from quotes: {', '.join(missing)}"
        return TriageResult(PRIORITY_HIGH, reason)

    return TriageResult(PRIORITY_LOW, "answer terms supported by quotes")


__all__ = ["TriageResult", "triage_submission"]
