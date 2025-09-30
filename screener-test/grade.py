cat > grader/grade.py << 'EOF'
import json, re, sys

MCQ_KEY = {"q1": "B", "q2": "B", "q3": "C", "q4": "C"}
PASS_TOTAL = 5
PERCENT_RE = re.compile(r"^\s*\d{1,3}(?:\.\d+)?\s*%?\s*$")
SEC_DOMAIN_RE = re.compile(r"^https://(www\.)?sec\.gov/", re.I)

def words(s): return len(re.findall(r"\b\w+\b", s or ""))

def normalize_percent(s):
    s = (s or "").strip()
    return s if s.endswith("%") else (s + "%" if s else s)

def validate_q5_fields(q5):
    notes, ok = [], True
    if not q5: return False, ["missing q5 block"]
    ans = normalize_percent(q5.get("answer",""))
    if not PERCENT_RE.match(ans): ok, notes = False, notes + ["answer not a percent"]
    if words(q5.get("quote","")) > 30: ok, notes = False, notes + ["quote > 30 words"]
    if not isinstance(q5.get("page",None), int) or q5["page"] <= 0: ok, notes = False, notes + ["invalid page"]
    if not SEC_DOMAIN_RE.match(q5.get("url","")): ok, notes = False, notes + ["non-SEC URL"]
    if not q5.get("section"): ok, notes = False, notes + ["missing section"]
    return ok, notes

def build_judge_prompt(q5):
    return f"""
You are grading a candidate’s answer using ONLY the provided evidence from an SEC filing.

[QUESTION]
What percentage of revenue came from customers outside the United States in the second quarter of fiscal year 2026?

[ANSWER]
{normalize_percent(q5.get('answer',''))}

[EVIDENCE]
Section/Note: {q5.get('section','')}
Quote (≤30 words): "{q5.get('quote','')}"
Page: {q5.get('page','')}
URL: {q5.get('url','')}

Return JSON ONLY with integer scores 1–5 and a short reason:
{{
  "factuality": X,
  "citation": Y,
  "clarity": Z,
  "safety": 5,
  "reason": "one short sentence"
}}
""".strip()

def call_llm_judge(prompt):
    # TODO: replace with your LLM API call.
    # Demo heuristic: pass only if '50%' appears in both answer and quote.
    has_50_answer = "50%" in prompt.split("[ANSWER]")[1]
    has_50_quote = "50%" in prompt.split('Quote (≤30 words): "')[1]
    if has_50_answer and has_50_quote:
        return {"factuality":5,"citation":5,"clarity":5,"safety":5,"reason":"answer matches quote"}
    return {"factuality":2,"citation":3,"clarity":3,"safety":5,"reason":"mismatch or weak citation"}

def main(in_path, out_path):
    with open(in_path, "r", encoding="utf-8") as f_in, open(out_path, "w", encoding="utf-8") as f_out:
        for line in f_in:
            sub = json.loads(line)
            notes = []
            mcq_correct = sum(1 for k,v in MCQ_KEY.items() if sub.get(k,"").strip().upper() == v)
            total_points = mcq_correct
            q5 = sub.get("q5")
            valid, vnotes = validate_q5_fields(q5)
            notes += vnotes
            q5_scores = None
            if valid:
                prompt = build_judge_prompt(q5)
                q5_scores = call_llm_judge(prompt)
                q5_pass = (
                    q5_scores.get("factuality",0) >= 5 and
                    q5_scores.get("citation",0)   >= 4 and
                    q5_scores.get("clarity",0)    >= 4
                )
                if q5_pass: total_points += 2
                else: notes.append("q5_judge_fail")
            else:
                notes.append("q5_validation_fail")
            passed = total_points >= PASS_TOTAL
            out = {
                "candidate_id": sub.get("candidate_id"),
                "mcq_correct": mcq_correct,
                "q5_scores": q5_scores,
                "total_points": total_points,
                "passed": passed,
                "notes": notes
            }
            f_out.write(json.dumps(out) + "\n")

if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "grader/schema_examples/submissions.jsonl"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "grader/schema_examples/results.jsonl"
    main(in_path, out_path)
EOF
