from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import unicodedata
from uuid import uuid4

from .knowledge import Knowledge
from .selectors import ModelOutputError, ModelUnavailable, PROMPT_SHA256, PROMPT_VERSION


def capability_limit(question):
    text = " ".join(unicodedata.normalize("NFKC", question).casefold().split())
    if (re.search(r"\b(turn|switch|start|stop|activate|deactivate|run|set|change|adjust|disable|enable|bypass)\b.{0,60}\b(pump|relay|actuator|safety|setpoint)\b", text)
            or re.search(r"\b(pump|relay)\b.{0,25}\b(on|off)\b", text)):
        return "action_unavailable", "This assistant cannot execute device actions. Use the authenticated app and its confirmation/safety checks."
    if (re.search(r"\b(current|latest|now|today|my|our)\b", text)
            and re.search(r"\b(ph|ec|sensors?|readings?|temperatures?|alerts?|water levels?)\b", text)):
        return "live_data_unavailable", "This assistant cannot read live sensor data or alerts yet. Check the dashboard."
    if re.search(r"\b(diagnose|diagnosis of|identify the disease in|analyse this photo|analyze this photo)\b", text):
        return "diagnosis_unavailable", "This assistant cannot diagnose a plant or inspect an image. Camera detections are only hints."
    return None


class Assistant:
    def __init__(self, selector, knowledge=None, trace_path=None):
        self.selector = selector
        self.knowledge = knowledge or Knowledge(public_only=selector.mode == "gemini")
        if selector.mode == "gemini" and not self.knowledge.public_only:
            raise ValueError("Gemini requires the public garden corpus")
        self.trace_path = Path(trace_path) if trace_path else None

    def ask(self, question):
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
            raise ValueError("question must contain 1–2000 characters")
        question = question.strip()
        started = time.monotonic()
        self.selector.last_metadata = {}
        result = {"request_id": str(uuid4()), "status": "insufficient_evidence",
                  "answer": "I don't know from the curated sources available here.", "citations": []}
        metadata = {"mode": self.selector.mode, "requested_model": self.selector.model,
                    "corpus_version": self.knowledge.version, "corpus_sha256": self.knowledge.fingerprint,
                    "prompt_version": PROMPT_VERSION if self.selector.mode != "extractive" else None,
                    "prompt_sha256": PROMPT_SHA256 if self.selector.mode != "extractive" else None,
                    "retrieved_ids": [], "selected_ids": [], "tools": [], "generation_requested": False,
                    "question_characters": len(question),
                    "corpus_scope": "public-garden" if self.knowledge.public_only else "full"}
        boundary = capability_limit(question)
        if boundary:
            result["status"], result["answer"] = boundary
        else:
            candidates = self.knowledge.retrieve(question)
            metadata["retrieved_ids"] = [p["id"] for p in candidates]
            if candidates:
                try:
                    selection = self.selector.select(question, candidates)
                    ids = selection.get("passage_ids") if isinstance(selection, dict) else None
                    if (not isinstance(selection, dict) or set(selection) != {"passage_ids"}
                            or not isinstance(ids, list) or len(ids) > 2
                            or any(not isinstance(key, str) for key in ids)
                            or len(set(ids)) != len(ids)
                            or any(key not in metadata["retrieved_ids"] for key in ids)):
                        raise ModelOutputError("selection contains invalid evidence IDs or extra fields")
                    if ids:
                        citations = []
                        for key in ids:
                            passage = self.knowledge.passages[key]
                            source = self.knowledge.sources[passage["source_id"]]
                            citations.append({"passage_id": key, "source_id": source["id"],
                                              "title": source["title"], "url": source["url"],
                                              "text": passage["text"]})
                        result.update(status="answered", citations=citations,
                                      answer="\n\n".join(f"{c['text']} [{c['passage_id']}]({c['url']})" for c in citations))
                        metadata["selected_ids"] = ids
                except ModelUnavailable as error:
                    messages = {
                        "invalid_request": "The provider rejected the request configuration.",
                        "invalid_key": "Check GEMINI_API_KEY.",
                        "access_denied": "Check the API key permissions and project access.",
                        "quota_exhausted": "Provider quota or prepaid credits are exhausted. Check project limits and billing.",
                        "model_not_found": "The requested model is unavailable to this API key. Choose another model ID.",
                        "provider_unavailable": "The provider is temporarily unavailable. Try again later.",
                        "connection_failed": "The provider could not be reached. Check your connection.",
                    }
                    code = error.code if error.code in messages else "unavailable"
                    metadata["provider_error"] = code
                    message = messages.get(code, "The selected model is unavailable.")
                    result.update(status="model_unavailable", answer=message + " No answer was generated.")
                except ModelOutputError:
                    result.update(status="invalid_model_output", answer="The model did not return valid source selections. No answer was generated.")
        for key in ("generation_requested", "baseline", "resolved_model", "model_digest", "options",
                    "prompt_eval_count", "eval_count", "total_duration", "promptTokenCount",
                    "candidatesTokenCount", "totalTokenCount", "thoughtsTokenCount"):
            if key in self.selector.last_metadata:
                metadata[key] = self.selector.last_metadata[key]
        metadata["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
        result["metadata"] = metadata
        if self.trace_path:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            # No question, answer text, credentials, tokens, conversation or device data.
            trace = {"request_id": result["request_id"], "status": result["status"],
                     "timestamp": datetime.now(timezone.utc).isoformat(), **metadata}
            with self.trace_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(trace, ensure_ascii=False, allow_nan=False) + "\n")
        return result
