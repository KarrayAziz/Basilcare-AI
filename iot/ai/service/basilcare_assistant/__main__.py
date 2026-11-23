import argparse
import json
import os
from pathlib import Path
import sys

from .assistant import Assistant
from .evaluation import DEFAULT_CASES, evaluate
from .knowledge import DEFAULT_CORPUS, Knowledge
from .selectors import ExtractiveSelector, OllamaSelector


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only, cited BasilCare Q&A. No model is downloaded or started.")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=("ollama", "extractive"), default="ollama")
    common.add_argument("--model", default=os.environ.get("OLLAMA_MODEL"), help="already installed local model name")
    common.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    common.add_argument("--timeout", type=float, default=60)
    common.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ask = commands.add_parser("ask", parents=[common])
    ask.add_argument("question")
    ask.add_argument("--trace", type=Path, help="optional local metadata-only JSONL file")
    ask.add_argument("--json", action="store_true")
    bench = commands.add_parser("evaluate", parents=[common])
    bench.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    bench.add_argument("--out", required=True, type=Path, help="new output directory, never overwritten")
    args = parser.parse_args(argv)
    try:
        selector = (ExtractiveSelector() if args.mode == "extractive" else
                    OllamaSelector(args.model, args.ollama_url, args.timeout))
        assistant = Assistant(selector, Knowledge(args.corpus), getattr(args, "trace", None))
        if args.command == "evaluate":
            report = evaluate(assistant, args.cases, args.out)
            print(f"{report['mode']}: {report['passed']}/{report['total']} cases passed; report: {args.out / 'evaluation.md'}")
            return 0 if report["passed_all"] else 2
        result = assistant.ask(args.question)
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result["answer"])
        return 1 if result["status"] in {"model_unavailable", "invalid_model_output"} else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Assistant input/report error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
