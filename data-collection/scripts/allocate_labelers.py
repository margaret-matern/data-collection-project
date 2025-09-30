#!/usr/bin/env python3
"""Allocate prompt labeling tasks across the B/C labeling pool."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

TYPE_KEY_MAP = {
    "A": "A",
    "B": "B",
    "C": "C",
    "C-EXT": "C-Extended",
    "C-EXTENDED": "C-Extended",
}


@dataclass
class PromptTask:
    prompt_id: str
    prompt_type: str
    minutes: float


@dataclass
class Labeler:
    id: str
    name: str
    hours_available: float
    focus: List[str]

    @property
    def minutes_available(self) -> float:
        return self.hours_available * 60


@dataclass
class Assignment:
    labeler: Labeler
    tasks: List[PromptTask]

    @property
    def minutes_committed(self) -> float:
        return sum(task.minutes for task in self.tasks)

    @property
    def remaining_minutes(self) -> float:
        return self.labeler.minutes_available - self.minutes_committed


def load_time_model(path: Path) -> Dict[str, float]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {str(k): float(v) for k, v in data.items()}


def load_labelers(path: Path) -> List[Labeler]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    labelers = []
    for entry in data.get("labelers", []):
        labelers.append(
            Labeler(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                hours_available=float(entry.get("hours_available", 0)),
                focus=[focus.upper() for focus in entry.get("focus", [])],
            )
        )
    return labelers


def load_prompts(path: Path, time_model: Dict[str, float]) -> List[PromptTask]:
    tasks: List[PromptTask] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            payload = json.loads(line)
            raw_type = payload.get("type", "").upper()
            normalized = TYPE_KEY_MAP.get(raw_type, raw_type)
            minutes = time_model.get(normalized)
            if minutes is None:
                raise KeyError(f"No time model entry for prompt type {normalized}")
            tasks.append(PromptTask(prompt_id=payload["prompt_id"], prompt_type=normalized, minutes=minutes))
    return tasks


def allocate(tasks: List[PromptTask], labelers: List[Labeler]) -> List[Assignment]:
    assignments = [Assignment(labeler=labeler, tasks=[]) for labeler in labelers]
    # Sort tasks longest first to balance workload
    tasks_sorted = sorted(tasks, key=lambda t: t.minutes, reverse=True)
    for task in tasks_sorted:
        assignments.sort(key=lambda a: a.remaining_minutes, reverse=True)
        target = assignments[0]
        if target.remaining_minutes <= 0:
            logging.warning("All labelers are fully allocated; task %s remains", task.prompt_id)
            target.tasks.append(task)
        else:
            target.tasks.append(task)
    return assignments


def summarize(assignments: List[Assignment]) -> Dict[str, Dict[str, float]]:
    summary: Dict[str, Dict[str, float]] = {}
    for assignment in assignments:
        type_totals: Dict[str, float] = {}
        for task in assignment.tasks:
            type_totals.setdefault(task.prompt_type, 0.0)
            type_totals[task.prompt_type] += task.minutes
        summary[assignment.labeler.id] = {
            "name": assignment.labeler.name,
            "hours_committed": assignment.minutes_committed / 60,
            "hours_remaining": assignment.remaining_minutes / 60,
            "type_breakdown": type_totals,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path, default=Path("data/prompts/prompts.jsonl"))
    parser.add_argument("--labelers", type=Path, default=Path("config/labelers.yml"))
    parser.add_argument("--time-model", type=Path, default=Path("config/time_model.yml"))
    parser.add_argument("--out", type=Path, default=Path("data/allocations/plan.json"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    time_model = load_time_model(args.time_model)
    labelers = load_labelers(args.labelers)
    tasks = load_prompts(args.prompts, time_model)

    assignments = allocate(tasks, labelers)
    summary = summarize(assignments)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump({"assignments": summary}, f, indent=2)

    total_minutes = sum(task.minutes for task in tasks)
    total_capacity = sum(labeler.minutes_available for labeler in labelers)
    logging.info(
        "Allocated %.1f hours of work across %.1f hours of capacity",
        total_minutes / 60,
        total_capacity / 60,
    )


if __name__ == "__main__":
    main()
