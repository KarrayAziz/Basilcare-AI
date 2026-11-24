"""Small, versioned regression cases. Baseline scores are never labelled LLM quality scores."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .selectors import PROMPT_SHA256, PROMPT_VERSION

PUBLIC_CASES = Path(__file__).resolve().parents[1] / "evaluation" / "public-garden.json"
DEFAULT_CASES = Path(__file__).resolve().parents[1] / "evaluation" / "cases.json"


def citation_integrity(result, knowledge):
    citations = result["citations"]
    if result["status"] != "answered":
        return not citations
    if not citations:
        return False
    for citation in citations:
        passage = knowledge.passages.get(citation["passage_id"])
        if not passage or citation["text"] != passage["text"]:
            return False
        source = knowledge.sources[passage["source_id"]]
        if citation["url"] != source["url"] or citation["source_id"] != source["id"]:
            return False
    expected_answer = "\n\n".join(f"{c['text']} [{c['passage_id']}]({c['url']})" for c in citations)
    return result["answer"] == expected_answer


def evaluate(assistant, cases_path, out):
    cases_path, out = Path(cases_path), Path(out)
    raw = cases_path.read_bytes()
    specification = json.loads(raw)
    cases = specification["cases"]
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("evaluation needs uniquely identified cases")
    for case in cases:
        if (not isinstance(case.get("question"), str) or not case["question"].strip()
                or not isinstance(case.get("expected_status"), str)
                or not isinstance(case.get("expected_passage_ids"), list)
                or any(key not in assistant.knowledge.passages for key in case["expected_passage_ids"])):
            raise ValueError("invalid evaluation case")
    out.mkdir(parents=True, exist_ok=False)
    assistant.trace_path = out / "traces.jsonl"
    rows, digests, versions = [], set(), set()
    token_usage = {}
    elapsed_ms = 0.0
    generation_requests = 0
    for case in cases:
        result = assistant.ask(case["question"])
        ids = [c["passage_id"] for c in result["citations"]]
        integrity = citation_integrity(result, assistant.knowledge)
        correct = (result["status"] == case["expected_status"]
                   and set(ids) == set(case["expected_passage_ids"]) and integrity)
        rows.append({"case_id": case["id"], "category": case["category"],
                     "expected_status": case["expected_status"], "actual_status": result["status"],
                     "expected_passage_ids": case["expected_passage_ids"], "actual_passage_ids": ids,
                     "citation_integrity": integrity, "passed": correct, "request_id": result["request_id"]})
        if result["metadata"].get("model_digest"):
            digests.add(result["metadata"]["model_digest"])
        generation_requests += bool(result["metadata"].get("generation_requested"))
        metadata = result["metadata"]
        if metadata.get("resolved_model"):
            versions.add(metadata["resolved_model"])
        elapsed_ms += metadata["elapsed_ms"]
        for field in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount", "thoughtsTokenCount",
                      "prompt_eval_count", "eval_count"):
            if field in metadata:
                token_usage[field] = token_usage.get(field, 0) + metadata[field]
    passed = sum(row["passed"] for row in rows)
    errors = sum(row["actual_status"] in {"model_unavailable", "invalid_model_output"} for row in rows)
    consistent = len(digests) <= 1
    version_consistent = len(versions) <= 1
    report = {"schema_version": 1, "timestamp": datetime.now(timezone.utc).isoformat(),
              "mode": assistant.selector.mode, "requested_model": assistant.selector.model,
              "prompt_version": PROMPT_VERSION if assistant.selector.mode != "extractive" else None,
              "prompt_sha256": PROMPT_SHA256 if assistant.selector.mode != "extractive" else None,
              "corpus_version": assistant.knowledge.version, "corpus_sha256": assistant.knowledge.fingerprint,
              "cases_version": specification["version"], "cases_sha256": hashlib.sha256(raw).hexdigest(),
              "resolved_models": sorted(versions), "model_version_consistent": version_consistent,
              "corpus_scope": "public-garden" if assistant.knowledge.public_only else "full",
              "token_usage": token_usage, "elapsed_ms": round(elapsed_ms, 3),
              "model_digests": sorted(digests), "model_digest_consistent": consistent,
              "generation_requests": generation_requests, "total": len(rows), "passed": passed,
              "case_pass_rate": passed / len(rows), "model_errors": errors, "cases": rows}
    report["passed_all"] = (passed == len(rows) and consistent and version_consistent and not errors
                            and (assistant.selector.mode == "extractive" or generation_requests > 0))
    (out / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Assistant regression evaluation", "", f"Mode: **{report['mode']}**", "",
             f"Corpus scope: **{report['corpus_scope']}**",
             f"Resolved models: {report['resolved_models']}; stable versions: {version_consistent}",
             f"Token usage: {token_usage}; total elapsed ms: {report['elapsed_ms']}",
             f"Cases passed: {passed}/{len(rows)}", f"Overall pass: **{report['passed_all']}**",
             f"Model errors: {errors}; stable model digest: {consistent}; generation requests: {generation_requests}", "",
             "| Case | Expected status | Actual status | Passed |", "|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['case_id']} | {row['expected_status']} | {row['actual_status']} | {row['passed']} |")
    lines += ["", "These small regression cases do not establish general agronomic/LLM quality.",
              "Extractive mode does not run an LLM. Gemini sends questions/public garden notes to Google; Ollama runs locally.",
              "Questions, full prompts, responses and credentials are not stored in these reports/traces."]
    (out / "evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
