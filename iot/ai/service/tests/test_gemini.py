"""Offline protocol tests; fixture model replies are not actual Gemini quality scores."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE))
from basilcare_assistant.assistant import Assistant
from basilcare_assistant.evaluation import DEFAULT_CASES, PUBLIC_CASES, evaluate
from basilcare_assistant.gemini import GeminiSelector, load_api_key, request_gemini
from basilcare_assistant.knowledge import DEFAULT_CORPUS, Knowledge
from basilcare_assistant.selectors import ModelUnavailable, ModelOutputError, PROMPT_SHA256

SECRET = "fixture-key-not-a-real-secret"


class FakeGemini:
    def __init__(self, content=None, finish="STOP", parts=None):
        self.calls = []
        self.content, self.finish, self.parts = content, finish, parts

    def __call__(self, model, body, key, timeout):
        self.calls.append((model, body, key, timeout))
        context = json.loads(body["contents"][0]["parts"][0]["text"])
        content = self.content or json.dumps({"passage_ids": [context["passages"][0]["id"]]})
        return {"modelVersion": "gemini-fixture-001", "candidates": [{"finishReason": self.finish,
                "content": {"parts": self.parts if self.parts is not None else [{"text": content}]}}],
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 10, "totalTokenCount": 110}}


class GeminiTest(unittest.TestCase):
    def test_secret_loading_is_literal_environment_first_and_not_sourced(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / ".env"
            marker = Path(tmp) / "should-not-exist"
            path.write_text(f"OTHER=$(touch {marker})\nGEMINI_API_KEY='{SECRET}'\n")
            self.assertEqual(load_api_key(path), SECRET)
            self.assertFalse(marker.exists())
            with patch.dict(os.environ, {"GEMINI_API_KEY": "environment-key"}):
                self.assertEqual(load_api_key(path), "environment-key")
            for entry in ("", 'GEMINI_API_KEY=""', "GEMINI_API_KEY=has spaces"):
                path.write_text(entry)
                with self.assertRaises(ValueError):
                    load_api_key(path)

    def test_cloud_retrieval_filters_project_content_before_ranking_and_hashing(self):
        knowledge = Knowledge(public_only=True)
        self.assertTrue(all(p["scope"] == "garden" for p in knowledge.passages.values()))
        self.assertNotIn("pump-confirmation", knowledge.passages)
        self.assertNotIn("camera-hints", knowledge.passages)
        self.assertNotEqual(knowledge.fingerprint, Knowledge().fingerprint)
        fake = FakeGemini()
        assistant = Assistant(GeminiSelector(SECRET, transport=fake))
        result = assistant.ask("How should I prune basil? Also confirmation pump camera")
        self.assertEqual(result["status"], "answered")
        wire = json.dumps(fake.calls[0][1])
        self.assertNotIn("pump-confirmation", wire)
        self.assertNotIn("camera-hints", wire)
        self.assertNotIn(SECRET, wire)
        self.assertEqual(result["metadata"]["prompt_sha256"], PROMPT_SHA256)
        with self.assertRaises(ValueError):
            Assistant(GeminiSelector(SECRET), Knowledge())
        with self.assertRaises(ValueError):
            GeminiSelector(SECRET).select("help", [Knowledge().passages["pump-confirmation"]])

    def test_structured_protocol_and_privacy_of_reports_and_traces(self):
        fake = FakeGemini()
        selector = GeminiSelector(SECRET, transport=fake)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report"
            report = evaluate(Assistant(selector), PUBLIC_CASES, out)
            self.assertTrue(report["passed_all"])
            self.assertEqual(report["total"], 8)
            self.assertEqual(report["generation_requests"], 5)
            self.assertEqual(report["token_usage"]["totalTokenCount"], 550)
            self.assertEqual(report["resolved_models"], ["gemini-fixture-001"])
            self.assertEqual(report["prompt_sha256"], PROMPT_SHA256)
            self.assertEqual(report["corpus_scope"], "public-garden")
            files = ''.join(p.read_text() for p in out.iterdir())
            self.assertNotIn(SECRET, files)
            self.assertNotIn("What light does basil prefer?", files)
            self.assertNotIn(Knowledge().passages["basil-light"]["text"], files)
        body = fake.calls[0][1]
        self.assertNotIn("tools", body)
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(body["generationConfig"]["responseSchema"]["properties"]["passage_ids"]["maxItems"], 2)

    def test_opaque_provider_signature_is_accepted_but_never_traced(self):
        fake = FakeGemini(parts=[{"text": '{"passage_ids":["basil-light"]}',
                                  "thoughtSignature": "opaque-provider-signature"}])
        result = Assistant(GeminiSelector(SECRET, transport=fake)).ask("basil light")
        self.assertEqual(result["status"], "answered")
        self.assertNotIn("opaque-provider-signature", json.dumps(result))

    def test_bad_output_tools_blocked_and_missing_versions_fail_closed(self):
        for fake in (FakeGemini(content="not-json"), FakeGemini(content='{"passage_ids":["fake"]}'),
                     FakeGemini(content='{"passage_ids":["basil-light"],"answer":"extra"}'),
                     FakeGemini(finish="MAX_TOKENS"), FakeGemini(finish="SAFETY"),
                     FakeGemini(parts=[{"functionCall": {"name": "pump"}}])):
            with self.subTest(fake=fake):
                result = Assistant(GeminiSelector(SECRET, transport=fake)).ask("basil light")
                self.assertEqual(result["status"], "invalid_model_output")
                self.assertFalse(result["citations"])
        fake = FakeGemini()
        def missing_version(*args):
            result = fake(*args)
            result.pop("modelVersion")
            return result
        self.assertEqual(Assistant(GeminiSelector(SECRET, transport=missing_version)).ask("basil light")["status"],
                         "invalid_model_output")

    def test_full_project_evaluation_is_rejected_before_any_cloud_request(self):
        fake = FakeGemini()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                evaluate(Assistant(GeminiSelector(SECRET, transport=fake)), DEFAULT_CASES, Path(tmp) / "rejected")
        self.assertEqual(fake.calls, [])

    def test_version_changes_and_zero_model_calls_cannot_claim_a_model_pass(self):
        fake = FakeGemini()
        def changed(*args):
            result = fake(*args)
            result["modelVersion"] += str(len(fake.calls))
            return result
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Assistant(GeminiSelector(SECRET, transport=changed)), PUBLIC_CASES, Path(tmp) / "mixed")
            self.assertEqual(report["passed"], 8)
            self.assertFalse(report["model_version_consistent"])
            self.assertFalse(report["passed_all"])
            path = Path(tmp) / "cases.json"
            data = json.loads(PUBLIC_CASES.read_text())
            data["cases"] = [c for c in data["cases"] if c["category"] == "unsupported"]
            path.write_text(json.dumps(data))
            report = evaluate(Assistant(GeminiSelector(SECRET)), path, Path(tmp) / "no-calls")
            self.assertFalse(report["passed_all"])

    def test_transport_has_fixed_destination_header_key_and_sanitized_errors(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = b'{"ok":true}'
        with patch("basilcare_assistant.gemini.build_opener", return_value=opener):
            self.assertEqual(request_gemini("gemini-fixture", {}, SECRET, 5), {"ok": True})
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-fixture:generateContent")
            self.assertEqual(request.get_header("X-goog-api-key"), SECRET)
            self.assertNotIn(SECRET, request.full_url)
            for status, code in ((400,"invalid_request"),(401,"invalid_key"),(403,"access_denied"),
                                 (402,"quota_exhausted"),(404,"model_not_found"),(429,"quota_exhausted"),
                                 (503,"provider_unavailable")):
                opener.open.side_effect = HTTPError(request.full_url,status,SECRET,{},io.BytesIO(SECRET.encode()))
                with self.assertRaises(ModelUnavailable) as context:
                    request_gemini("gemini-fixture", {}, SECRET, 5)
                self.assertEqual(context.exception.code, code)
                self.assertNotIn(SECRET,str(context.exception))
            opener.open.side_effect = URLError(SECRET)
            with self.assertRaises(ModelUnavailable) as context:
                request_gemini("gemini-fixture", {}, SECRET, 5)
            self.assertEqual(context.exception.code,"connection_failed")
            self.assertNotIn(SECRET,str(context.exception))
            opener.open.side_effect = None
            response.read.return_value = b"x" * 262145
            with self.assertRaises(ModelOutputError):
                request_gemini("gemini-fixture",{},SECRET,5)

    def test_failures_are_clear_and_do_not_fall_back_or_leak_exception_details(self):
        for code, expected in (("quota_exhausted", "billing"), ("invalid_key", "GEMINI_API_KEY"),
                               ("provider_unavailable", "temporarily")):
            def failed(*args): raise ModelUnavailable(SECRET, code=code)
            result = Assistant(GeminiSelector(SECRET, transport=failed)).ask("basil light")
            self.assertEqual(result["status"],"model_unavailable")
            self.assertIn(expected,result["answer"])
            self.assertNotIn(SECRET,json.dumps(result))
            self.assertEqual(result["metadata"]["provider_error"],code)
        for model in ("https://evil.example", "../path", "gemini-foo?key=secret", "gemini-foo/bar"):
            with self.assertRaises(ValueError): GeminiSelector(SECRET,model=model)
        with self.assertRaises(ValueError): GeminiSelector(SECRET,timeout=0)
        command = [sys.executable,"-m","basilcare_assistant","ask","basil light","--mode","gemini"]
        with patch.dict(os.environ,{"GEMINI_API_KEY":""}):
            result = subprocess.run(command,cwd=SERVICE,capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn("GEMINI_API_KEY",result.stderr)


if __name__ == '__main__':
    unittest.main()
