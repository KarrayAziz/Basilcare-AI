"""Internal garden-Q&A service. Only the authenticated Java API should call it."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import BoundedSemaphore

from .assistant import Assistant
from .gemini import GeminiSelector, load_api_key

MAX_BODY = 16384
SLOTS = BoundedSemaphore(2)


def answer(question):
    # Fresh selector per request: mutable provider metadata must never cross users.
    result = Assistant(GeminiSelector(load_api_key(), model=os.environ.get(
        "GEMINI_MODEL", "gemini-3.1-flash-lite"), timeout=25)).ask(question)
    return {"status": result["status"],
            "answer": "\n\n".join(c["text"] for c in result["citations"]) or result["answer"],
            "citations": [{k: c[k] for k in ("title", "url", "text")} for c in result["citations"]]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No questions, answers, authorization headers or provider bodies in access logs.

    def reply(self, status, payload):
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        key = os.environ.get("ASSISTANT_SERVICE_KEY", "")
        supplied = self.headers.get("Authorization", "")
        if len(key) < 24 or not hmac.compare_digest(supplied.encode(), ("Bearer " + key).encode()):
            self.reply(401, {"message": "Internal service authentication required."})
            return
        if self.path != "/ask":
            self.reply(404, {"message": "Not found."})
            return
        if self.headers.get("Transfer-Encoding") or self.headers.get_content_type() != "application/json":
            self.reply(400, {"message": "A JSON request with Content-Length is required."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.reply(413, {"message": "Question is too large."})
                return
            self.connection.settimeout(5)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError()
            body = json.loads(raw)
            question = body.get("question") if isinstance(body, dict) and set(body) == {"question"} else None
            if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
                raise ValueError()
        except (ValueError, OSError):
            self.reply(400, {"message": "Enter a question between 1 and 2000 characters."})
            return
        if not SLOTS.acquire(blocking=False):
            self.reply(503, {"message": "The assistant is busy. Try again shortly."})
            return
        try:
            try:
                result = answer(question)
                self.reply(503 if result["status"] == "model_unavailable" else
                           502 if result["status"] == "invalid_model_output" else 200, result)
            except (ValueError, OSError):
                self.reply(503, {"message": "The assistant is not configured. Ask an administrator to check it."})
        finally:
            SLOTS.release()


def main():
    server = ThreadingHTTPServer(("0.0.0.0", 8090), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
