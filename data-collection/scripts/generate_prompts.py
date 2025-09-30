#!/usr/bin/env python3
"""Generate question prompts from indexed filings."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import openai

TARGET_COUNTS = {"A": 30, "B": 50, "C": 45}
C_EXTENDED_COUNT = 5
MAX_STANDARD_C_FILINGS = 6

SYSTEM_PROMPT = """You are an expert financial analyst creating grounded question prompts for annotators. Each prompt must cite the provided evidence and request a detailed answer."""

TEMPLATE_PROMPT = """Create a question for labelers using the provided evidence. The question must require grounded reasoning, reference the company names, and include expected answer bullet points."""


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    section_hint: Optional[str]
    text: str


class PromptGenerator:
    def __init__(self, model: str = "gpt-4o-mini", seed: int = 13):
        self.model = model
        self.seed = seed
        random.seed(seed)
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY".lower())
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY must be set in the environment to generate prompts via the OpenAI API."
            )
        openai.api_key = api_key

    def llm_prompt(self, prompt_type: str, evidence: List[Chunk]) -> str:
        joined = "\n\n".join(
            f"[{chunk.doc_id} :: {chunk.section_hint or 'Unknown Section'}]\n{chunk.text}" for chunk in evidence
        )
        completion = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Prompt type: {prompt_type}. {TEMPLATE_PROMPT}\n\nEvidence:\n{joined}\n\nFormat as:"
                        "\nQuestion:\n- ...\nExpected Answer Notes:\n- ..."
                    ),
                },
            ],
            temperature=0.7,
        )
        return completion.choices[0].message["content"].strip()

    def sample_evidence(self, chunks_by_doc: Dict[str, List[Chunk]], num_docs: int) -> List[Chunk]:
        doc_ids = random.sample(list(chunks_by_doc.keys()), num_docs)
        evidence: List[Chunk] = []
        for doc_id in doc_ids:
            evidence.append(random.choice(chunks_by_doc[doc_id]))
        return evidence

    def generate(self, chunks: List[Chunk]) -> List[dict]:
        chunks_by_doc: Dict[str, List[Chunk]] = {}
        for chunk in chunks:
            chunks_by_doc.setdefault(chunk.doc_id, []).append(chunk)

        outputs: List[dict] = []

        # Type A: single-document grounding
        for idx in range(TARGET_COUNTS["A"]):
            evidence = self.sample_evidence(chunks_by_doc, 1)
            prompt_text = self.llm_prompt("A", evidence)
            outputs.append(
                {
                    "prompt_id": f"A-{idx+1:03d}",
                    "type": "A",
                    "doc_ids": [chunk.doc_id for chunk in evidence],
                    "chunk_ids": [chunk.chunk_id for chunk in evidence],
                    "prompt": prompt_text,
                }
            )

        # Type B: two documents
        for idx in range(TARGET_COUNTS["B"]):
            evidence = self.sample_evidence(chunks_by_doc, min(2, len(chunks_by_doc)))
            prompt_text = self.llm_prompt("B", evidence)
            outputs.append(
                {
                    "prompt_id": f"B-{idx+1:03d}",
                    "type": "B",
                    "doc_ids": [chunk.doc_id for chunk in evidence],
                    "chunk_ids": [chunk.chunk_id for chunk in evidence],
                    "prompt": prompt_text,
                }
            )

        # Type C: mix of standard and extended
        c_extended_indices = set(random.sample(range(TARGET_COUNTS["C"]), k=C_EXTENDED_COUNT))
        for idx in range(TARGET_COUNTS["C"]):
            if idx in c_extended_indices:
                doc_count = min(len(chunks_by_doc), max(6, len(chunks_by_doc)))
                evidence = self.sample_evidence(chunks_by_doc, doc_count)
                prompt_label = "C-EXT"
            else:
                doc_count = min(MAX_STANDARD_C_FILINGS, len(chunks_by_doc))
                doc_count = max(2, doc_count)
                evidence = self.sample_evidence(chunks_by_doc, doc_count)
                prompt_label = "C"
            prompt_text = self.llm_prompt(prompt_label, evidence)
            outputs.append(
                {
                    "prompt_id": f"C-{idx+1:03d}",
                    "type": prompt_label,
                    "doc_ids": [chunk.doc_id for chunk in evidence],
                    "chunk_ids": [chunk.chunk_id for chunk in evidence],
                    "prompt": prompt_text,
                }
            )

        return outputs


def load_chunks(chunk_file: Path) -> List[Chunk]:
    chunks: List[Chunk] = []
    with chunk_file.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            chunk_id = payload.get("chunk_id") or f"chunk-{idx:05d}"
            chunk = Chunk(
                chunk_id=chunk_id,
                doc_id=payload["doc_id"],
                section_hint=payload.get("section_hint"),
                text=payload["text"],
            )
            chunks.append(chunk)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-file", type=Path, default=Path("data/docs/chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/prompts/prompts.jsonl"))
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    chunks = load_chunks(args.chunk_file)
    if not chunks:
        raise SystemExit("No chunks found; run index_filings.py first")

    generator = PromptGenerator(model=args.model, seed=args.seed)
    prompts = generator.generate(chunks)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for prompt in prompts:
            f.write(json.dumps(prompt) + "\n")

    logging.info("Generated %s prompts", len(prompts))


if __name__ == "__main__":
    main()
