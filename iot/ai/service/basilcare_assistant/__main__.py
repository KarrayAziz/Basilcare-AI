import argparse
import json
import os
from pathlib import Path
import sys

from .assistant import Assistant
from .evaluation import DEFAULT_CASES, PUBLIC_CASES, evaluate
from .knowledge import DEFAULT_CORPUS, Knowledge
from .selectors import ExtractiveSelector, OllamaSelector
from .gemini import DEFAULT_MODEL, GeminiSelector, load_api_key


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only, cited BasilCare Q&A. No model is downloaded or started.")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=("ollama", "extractive", "gemini"), default="ollama")
    common.add_argument("--model", help="provider model ID (Ollama: installed model; Gemini: defaults to " + DEFAULT_MODEL + ")")
    common.add_argument("--env-file", type=Path, help="Gemini only: read GEMINI_API_KEY literally; environment takes precedence")
    common.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    common.add_argument("--timeout", type=float, default=60)
    common.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ask = commands.add_parser("ask", parents=[common])
    ask.add_argument("question")
    ask.add_argument("--trace", type=Path, help="optional local metadata-only JSONL file")
    ask.add_argument("--json", action="store_true")
    bench = commands.add_parser("evaluate", parents=[common])
    bench.add_argument("--cases", type=Path, help="Gemini defaults to public-garden cases; local modes use full regression cases")
    bench.add_argument("--out", required=True, type=Path, help="new output directory, never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.env_file and args.mode != "gemini":
            raise ValueError("--env-file is only supported with --mode gemini")
        if args.mode == "gemini":
            selector = GeminiSelector(load_api_key(args.env_file),
                                      args.model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL, args.timeout)
        elif args.mode == "extractive":
            selector = ExtractiveSelector()
        else:
            selector = OllamaSelector(args.model or os.environ.get("OLLAMA_MODEL"), args.ollama_url, args.timeout)
        assistant = Assistant(selector, Knowledge(args.corpus, public_only=args.mode == "gemini"),
                              getattr(args, "trace", None))
        if args.command == "evaluate":
            report = evaluate(assistant, args.cases or (PUBLIC_CASES if args.mode == "gemini" else DEFAULT_CASES), args.out)
            print(f"{report['mode']}: {report['passed']}/{report['total']} cases passed; report: {args.out / 'evaluation.md'}")
            return 0 if report["passed_all"] else 2
        result = assistant.ask(args.question)
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result["answer"])
        return 1 if result["status"] in {"model_unavailable", "invalid_model_output"} else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Key loader/provider configuration messages never include secret values.
        print(f"Assistant input/report error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
