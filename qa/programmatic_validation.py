"""Programmatic validation utilities for QA stage 1.

This module exposes a small helper that checks basic structural
requirements for a submission prior to human or LLM review.  The goal is to
fail fast on obvious data quality problems (e.g., malformed citations or
non-EDGAR links) so review capacity is not wasted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse


@dataclass
class ValidationIssue:
    """Represents a single validation issue detected during stage 1."""

    field: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.field}: {self.message}"


REQUIRED_TOP_LEVEL_FIELDS: Tuple[str, ...] = (
    "prompt",
    "answer",
    "citations",
    "metadata",
)
REQUIRED_METADATA_FIELDS: Tuple[str, ...] = ("category", "requires_calc")
VALID_CATEGORIES = {"A", "B", "C", "C-Extended"}


def _word_count(text: str) -> int:
    return len(text.split())


def _is_sec_domain(url: str) -> bool:
    try:
        hostname = urlparse(url).hostname or ""
    except ValueError:
        return False
    return hostname.endswith("sec.gov")


def _ensure_iterable(value) -> Iterable:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return value
    return ()


def validate_submission(submission: Dict) -> Tuple[bool, List[ValidationIssue]]:
    """Validate a submission for stage 1 programmatic checks.

    Parameters
    ----------
    submission:
        Mapping representing a single QA submission.  The expected schema is
        intentionally lean and mirrors the data bundle produced in the
        deliverable stage.

    Returns
    -------
    tuple
        ``(is_valid, issues)`` where ``issues`` contains human-readable
        warnings describing the failure conditions.
    """

    issues: List[ValidationIssue] = []

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in submission:
            issues.append(ValidationIssue(field, "missing required field"))

    if issues:
        return False, issues

    metadata = submission.get("metadata", {}) or {}
    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            issues.append(ValidationIssue(f"metadata.{field}", "missing required field"))

    category = metadata.get("category")
    if category not in VALID_CATEGORIES:
        issues.append(
            ValidationIssue(
                "metadata.category",
                f"invalid category '{category}'. Expected one of {sorted(VALID_CATEGORIES)}",
            )
        )

    requires_calc = bool(metadata.get("requires_calc"))
    if requires_calc and not submission.get("calc"):
        issues.append(ValidationIssue("calc", "required calculation explanation missing"))

    citations = list(_ensure_iterable(submission.get("citations")))
    if not citations:
        issues.append(ValidationIssue("citations", "expected a non-empty list of citation objects"))
        return False, issues

    for idx, citation in enumerate(citations):
        prefix = f"citations[{idx}]"
        if not isinstance(citation, dict):
            issues.append(ValidationIssue(prefix, "expected mapping with citation fields"))
            continue

        quote = citation.get("quote", "") or ""
        if not quote:
            issues.append(ValidationIssue(f"{prefix}.quote", "quote is required"))
        elif _word_count(quote) > 30:
            issues.append(
                ValidationIssue(
                    f"{prefix}.quote",
                    f"quote has {_word_count(quote)} words (limit is 30)",
                )
            )

        page = citation.get("page")
        if page in (None, ""):
            issues.append(ValidationIssue(f"{prefix}.page", "page number is required"))
        else:
            try:
                page_value = int(page)
                if page_value <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                issues.append(
                    ValidationIssue(f"{prefix}.page", f"invalid page value '{page}' (positive integer required)")
                )

        url = citation.get("edgar_url", "") or ""
        if not url:
            issues.append(ValidationIssue(f"{prefix}.edgar_url", "EDGAR URL is required"))
        elif not _is_sec_domain(url):
            issues.append(
                ValidationIssue(
                    f"{prefix}.edgar_url",
                    "URL must be on the sec.gov domain",
                )
            )

        section = citation.get("section_or_note", "") or ""
        if not section:
            issues.append(ValidationIssue(f"{prefix}.section_or_note", "section or note is required"))

    return len(issues) == 0, issues


__all__ = ["ValidationIssue", "validate_submission"]
