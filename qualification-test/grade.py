#!/usr/bin/env python3
"""
Grades the Advanced Test:
- Auto-grades Q1–Q4 (MC)
- Validates presence/format of citations for Q5–Q8
- Checks quote length (<=30 words), page numeric, EDGAR URL domain
- Emits a machine-parseable JSON report and a JSONL for LLM judge triage on Q5/Q7/Q8

Inputs:
  advanced_responses.csv  (see questions.md for schema)
Outputs:
  grading_report.json     (summary + per-worker/per-item results)
  judge_payload.jsonl     (records for LLM triage on Q5/Q7/Q8)
"""

import csv, json, re, sys
from pathlib import Path
from collections import defaultdict

ANSWER_KEY = {
    "q1": "A",
    "q2": "A",
    "q3": "A",
    "q4": "A",
    "q6": "B",
}

SEC_RE = re.compile(r"https?://[^ ]*sec\.gov[^ ]*", re.I)

def word_count(text):
    return len(re.findall(r"\b\w+\b", text or ""))

def is_numeric_page(val):
    try:
        int(str(val).strip())
        return True
    except:
        return False

def citation_ok(section, page, quote, url):
    if not section or not str(section).strip():
        return False, "missing_section"
    if not is_numeric_page(page):
        return False, "bad_page"
    if not quote or word_count(quote) > 30:
        return False, "quote_len"
    if not url or not SEC_RE.search(url):
        return False, "bad_url"
    return True, None

def main():
    in_csv = Path("advanced_responses.csv")
    if not in_csv.exists():
        print("ERROR: advanced_responses.csv not found", file=sys.stderr)
        sys.exit(1)

    judge_out = Path("judge_payload.jsonl").open("w", encoding="utf-8")
    report = {
        "summary": {"workers": 0, "rows": 0, "mc_correct": 0, "mc_total": 0},
        "workers": {},
        "rows": []
    }

    per_worker = defaultdict(lambda: {"mc_correct":0,"mc_total":0,"rows":0,"issues":defaultdict(int)})

    with in_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        report["summary"]["workers"] = len(set())
        for row in reader:
            report["summary"]["rows"] += 1
            worker = row.get("worker_id","unknown").strip() or "unknown"
            per_worker[worker]["rows"] += 1

            # --- Grade MC: Q1,Q2,Q3,Q4,Q6 ---
            mc_checks = {}
            for q in ["q1","q2","q3","q4","q6"]:
                pred = (row.get(q,"") or "").strip().upper()
                gold = ANSWER_KEY.get(q)
                correct = (pred == gold)
                mc_checks[q] = {"pred": pred, "gold": gold, "correct": correct}
                if q in ["q1","q2","q3","q4"]:
                    per_worker[worker]["mc_total"] += 1
                    report["summary"]["mc_total"] += 1
                    if correct:
                        per_worker[worker]["mc_correct"] += 1
                        report["summary"]["mc_correct"] += 1

            # --- Validate Q5 citations (>=1) ---
            q5_citations_ok = True
            q5_issues = []
            ok, err = citation_ok(row.get("q5_section"), row.get("q5_page"), row.get("q5_quote"), row.get("q5_url"))
            if not ok:
                q5_citations_ok = False
                q5_issues.append(err)

            # --- Validate Q7 citations (>=1) ---
            q7_citations_ok = True
            q7_issues = []
            ok, err = citation_ok(row.get("q7_section"), row.get("q7_page"), row.get("q7_quote"), row.get("q7_url"))
            if not ok:
                q7_citations_ok = False
                q7_issues.append(err)

            # --- Validate Q8 citations (INTC + QCOM) ---
            q8_citations_ok = True
            q8_issues = []
            ok_i, err_i = citation_ok(row.get("q8_section_intc"), row.get("q8_page_intc"), row.get("q8_quote_intc"), row.get("q8_url_intc"))
            ok_q, err_q = citation_ok(row.get("q8_section_qcom"), row.get("q8_page_qcom"), row.get("q8_quote_qcom"), row.get("q8_url_qcom"))
            if not ok_i:
                q8_citations_ok = False
                q8_issues.append(f"INTC:{err_i}")
            if not ok_q:
                q8_citations_ok = False
                q8_issues.append(f"QCOM:{err_q}")

            # --- Build judge payload for Q5/Q7/Q8 (triage aid only) ---
            def add_judge(item_id, answer, cites, calc=None):
                payload = {
                    "item_id": item_id,
                    "answer": (answer or "").strip(),
                    "citations": [
                        {"section_or_note": s, "page": p, "quote": q, "edgar_url": u}
                        for (s,p,q,u) in cites if s or p or q or u
                    ]
                }
                if calc:
                    payload["calc"] = calc
                judge_out.write(json.dumps(payload, ensure_ascii=False) + "\n")

            add_judge(
                "Q5",
                row.get("q5_answer"),
                [(row.get("q5_section"), row.get("q5_page"), row.get("q5_quote"), row.get("q5_url"))]
            )
            add_judge(
                "Q7",
                row.get("q7_answer"),
                [(row.get("q7_section"), row.get("q7_page"), row.get("q7_quote"), row.get("q7_url"))]
            )
            add_judge(
                "Q8",
                row.get("q8_answer"),
                [
                    (row.get("q8_section_intc"), row.get("q8_page_intc"), row.get("q8_quote_intc"), row.get("q8_url_intc")),
                    (row.get("q8_section_qcom"), row.get("q8_page_qcom"), row.get("q8_quote_qcom"), row.get("q8_url_qcom")),
                ]
            )

            # --- Aggregate issues for worker stats ---
            for tag in q5_issues + q7_issues + q8_issues:
                per_worker[worker]["issues"][tag] += 1

            report["rows"].append({
                "worker_id": worker,
                "mc": mc_checks,
                "q5_citations_ok": q5_citations_ok,
                "q5_issues": q5_issues,
                "q7_citations_ok": q7_citations_ok,
                "q7_issues": q7_issues,
                "q8_citations_ok": q8_citations_ok,
                "q8_issues": q8_issues,
                "notes": row.get("notes","").strip()
            })

    judge_out.close()

    # Per-worker summary
    report["workers"] = {
        w: {
            "mc_correct": d["mc_correct"],
            "mc_total": d["mc_total"],
            "accuracy_mc": round(d["mc_correct"]/d["mc_total"], 3) if d["mc_total"] else None,
            "rows": d["rows"],
            "top_issues": sorted(d["issues"].items(), key=lambda x: -x[1])[:5],
        }
        for w,d in per_worker.items()
    }

    Path("grading_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote grading_report.json and judge_payload.jsonl")

if __name__ == "__main__":
    main()
