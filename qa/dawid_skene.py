"""Minimal Dawid–Skene implementation for reviewer consensus (stage 4).

The algorithm models each reviewer with a confusion matrix and infers the
latent "true" label for every item.  We focus on the PASS/FIX/REJECT triad, but
any discrete label space will work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, MutableMapping, Tuple


Label = str
ReviewerID = str
ItemID = str

DEFAULT_LABELS: Tuple[Label, ...] = ("PASS", "FIX", "REJECT")
SMOOTHING = 1e-3
MAX_ITERATIONS = 50
EPS = 1e-6


@dataclass
class Review:
    item_id: ItemID
    reviewer_id: ReviewerID
    label: Label


@dataclass
class ConsensusResult:
    item_id: ItemID
    label: Label
    posterior: Dict[Label, float]
    confidence: float
    needs_sme: bool


@dataclass
class DawidSkeneModel:
    priors: Dict[Label, float]
    confusion_matrices: Dict[ReviewerID, Dict[Label, Dict[Label, float]]]


ROUTING_THRESHOLDS = {
    "PASS": 0.80,
    "FIX": 0.70,
    "REJECT": 0.70,
}


def _normalize(dist: MutableMapping[Label, float]) -> None:
    total = sum(dist.values())
    if total <= 0:
        size = len(dist)
        for key in dist:
            dist[key] = 1.0 / size
        return
    inv_total = 1.0 / total
    for key in dist:
        dist[key] *= inv_total


def _initialize_priors(labels: Iterable[Label]) -> Dict[Label, float]:
    labels = list(labels)
    size = len(labels)
    return {label: 1.0 / size for label in labels}


def _initialize_confusion(reviewers: Iterable[ReviewerID], labels: Iterable[Label]) -> Dict[ReviewerID, Dict[Label, Dict[Label, float]]]:
    labels = list(labels)
    identity = {l: {obs: (1.0 if obs == l else SMOOTHING) for obs in labels} for l in labels}
    for row in identity.values():
        _normalize(row)
    return {reviewer: {l: row.copy() for l, row in identity.items()} for reviewer in reviewers}


def run_dawid_skene(reviews: Iterable[Review], labels: Iterable[Label] = DEFAULT_LABELS) -> Tuple[List[ConsensusResult], DawidSkeneModel]:
    reviews = list(reviews)
    if not reviews:
        return [], DawidSkeneModel({}, {})

    labels = tuple(labels)
    items = {review.item_id for review in reviews}
    reviewers = {review.reviewer_id for review in reviews}

    priors = _initialize_priors(labels)
    confusion = _initialize_confusion(reviewers, labels)

    # Posterior per item for each iteration.
    posteriors: Dict[ItemID, Dict[Label, float]] = {item: {label: 1.0 / len(labels) for label in labels} for item in items}

    for _ in range(MAX_ITERATIONS):
        # E-step: compute posteriors for each item.
        new_posteriors: Dict[ItemID, Dict[Label, float]] = {}
        for item in items:
            probs = {label: priors[label] for label in labels}
            for review in filter(lambda r, item=item: r.item_id == item, reviews):
                reviewer_matrix = confusion[review.reviewer_id]
                for label in labels:
                    probs[label] *= reviewer_matrix[label].get(review.label, SMOOTHING)
            _normalize(probs)
            new_posteriors[item] = probs

        delta = max(
            abs(new_posteriors[item][label] - posteriors[item][label])
            for item in items
            for label in labels
        )
        posteriors = new_posteriors

        if delta < EPS:
            break

        # M-step: update priors and confusion matrices.
        priors = {label: 0.0 for label in labels}
        for probs in posteriors.values():
            for label, prob in probs.items():
                priors[label] += prob
        _normalize(priors)

        for reviewer in reviewers:
            counts = {label: {obs: SMOOTHING for obs in labels} for label in labels}
            for review in filter(lambda r, reviewer=reviewer: r.reviewer_id == reviewer, reviews):
                probs = posteriors[review.item_id]
                for label in labels:
                    counts[label][review.label] += probs[label]
            for label in labels:
                _normalize(counts[label])
            confusion[reviewer] = counts

    results: List[ConsensusResult] = []
    for item, probs in posteriors.items():
        label = max(probs.items(), key=lambda kv: kv[1])[0]
        confidence = probs[label]
        threshold = ROUTING_THRESHOLDS.get(label, 1.0)
        needs_sme = confidence < threshold
        results.append(
            ConsensusResult(
                item_id=item,
                label=label,
                posterior=dict(probs),
                confidence=confidence,
                needs_sme=needs_sme,
            )
        )

    model = DawidSkeneModel(priors=priors, confusion_matrices=confusion)
    return results, model


__all__ = [
    "Review",
    "ConsensusResult",
    "DawidSkeneModel",
    "run_dawid_skene",
]
