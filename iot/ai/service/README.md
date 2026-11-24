# Cited basil-care assistant

The assistant is available in the signed-in Farmer PWA and through terminal commands.
The web path is Farmer PWA -> protected Java API -> internal Python service -> Gemini.
Only Python receives the Gemini key; the API forwards only the question and a dedicated
service credential. There is no MCP server, live sensor access, diagnosis or pump control.

## Gemini: notes as context, generated answers

Gemini receives **all five short public gardening notes** on every question. Python does
not first search for matching English keywords or reject a question based on word overlap.
The model interprets the question, writes a concise answer in the question's language,
and identifies up to two supporting notes. It can summarize, explain and translate the
notes. For example, “Comment dois-je tailler le basilic ?” can receive a French answer.

The instructions require answers supported by the notes, with an explanation of insufficient
context for unsupported requests. The assistant does not browse the web or fetch pages.
Only public garden notes from NC State and Utah State are included; project/pump/camera
notes are excluded before indexing/fingerprinting. Questions and those public notes are
sent to Google. Do not include private information. Google retention/billing rules apply.

The returned JSON contains `answer` and `passage_ids`. The application checks the schema,
answer length (1–4000 characters), allowed/nonduplicate IDs (at most two), complete provider
output and model version. Model-written URLs, tools and extra fields are rejected. Source
links come exclusively from saved references; the browser renders the answer as text.
An empty ID list gives status `insufficient_evidence` with the model's explanation.

These checks establish source provenance and output structure, **not semantic proof that
every generated claim follows the notes**. A model can still misinterpret context or cite
an irrelevant note. Review the answer/source and broaden evaluations before claiming general
agronomic quality. Garden soil advice must not become a hydroponic nutrient/reservoir target.
Capability refusals in Gemini mode are prompt instructions, not English keyword checks;
there are structurally no device tools or live-data clients to execute actions.

## Terminal usage

Python 3.10+ and the standard library suffice. From `iot/ai/service`:

```bash
python3 -m basilcare_assistant ask "Comment dois-je tailler le basilic ?" --mode gemini \
  --env-file ../../../deploy/.env --json
python3 -m basilcare_assistant evaluate --mode gemini \
  --env-file ../../../deploy/.env --out runs/gemini-context-001
```

`GEMINI_API_KEY` comes from the environment or an explicitly supplied ignored env file;
the environment wins. The loader reads only the literal key without sourcing/interpolating
shell code. Never put a real key in Git. The default model is `gemini-3.1-flash-lite`,
overridable with `--model` or `GEMINI_MODEL`. Ollama remains the default CLI provider unless
`--mode gemini` is specified. The website uses Gemini only.

Gemini uses a fixed Google HTTPS endpoint, a header API key, temperature 0 and a 768-token
output budget. Redirects, environment proxies, automatic retries and provider fallback are
disabled. CLI `--timeout` accepts 1–120 seconds (default 60); the internal service uses 25.
Provider/key/quota/billing/connection errors are sanitized; no upstream error bodies,
credentials, headers, provider signatures or question/answer text are written to traces.

## Local Ollama and explicit no-model baseline

These modes retain the earlier lexical retrieval and passage-selection behavior. They
return original notes with source links; **they do not provide Gemini's generated multilingual
context answers**. English capability checks and conservative hydroponic retrieval exclusions
remain here. No mode silently falls back to the baseline after a model error.

```bash
python3 -m basilcare_assistant ask "How should I prune basil?" --mode extractive
python3 -m basilcare_assistant evaluate --mode extractive --out runs/baseline-001
python3 -m basilcare_assistant ask "What light does basil prefer?" --model YOUR_INSTALLED_MODEL
python3 -m basilcare_assistant evaluate --model YOUR_INSTALLED_MODEL --out runs/local-model-001
```

Ollama must be separately installed/running. This helper never starts a model or downloads
weights. `OLLAMA_MODEL` can select an installed local model. `--ollama-url` defaults to
`http://127.0.0.1:11434`, accepting only loopback HTTP origins; cloud tags are rejected.
The adapter records `/api/tags` digests before/after `/api/chat`, rejecting changed weights,
tool calls, invalid IDs and incomplete output. Temperature 0/seed 2026 do not guarantee
identical results across hardware/runtimes. Extractive baseline selects the first match;
it does not run a language model or establish model quality.

## Corpus, traces and evaluation

`corpus/knowledge.json` contains seven original notes: five public garden topics and two
project-help topics available to local modes only. See `corpus/LICENSE.md` for attribution
and licensing; upstream articles/images are not relicensed or copied wholesale.

Gemini defaults to `evaluation/garden-context.json`: eleven public cases including English,
French, a semantic paraphrase and unsupported questions. **All eleven now call Gemini**;
unsupported questions are no longer blocked by lexical lookup. The full fifteen-case suite
remains for local modes. Custom cloud case files are explicit caller inputs: review their
questions first. Unknown expected source IDs are rejected before any API calls.

Reports check expected status/IDs and structural source integrity. Generated answers need
human review for language, relevance and factual grounding; source-ID scores alone do not
measure these. `evaluation/results/` contains separately labelled historical runs from the
older evidence-selection behavior. Do not compare those as if the prompt/context were unchanged.

Optional `ask --trace` and evaluation JSONL record request/status, context/source IDs, corpus
and prompt hashes/versions, model version, settings, timing and token counts. `context_ids`
records all public notes in Gemini mode; `retrieved_ids` is only lexical results for local
modes. Raw questions/answers/conversations are not stored. Cloud version strings are not
weight digests or proof of immutable provider behavior. Mixed versions/prompts, errors and
zero model calls cannot pass a model evaluation. New output directories are never overwritten;
`runs/` is Git-ignored. Ask exits 1 on configuration/model/output errors; evaluation exits
0 on pass, 2 on failed cases, and 1 on invalid inputs/reports.

## Website startup and limits

Keep `GEMINI_API_KEY` in ignored `deploy/.env`, then launch the updated checkout yourself:
`bash start.sh --build`. The script adds a dedicated random `ASSISTANT_SERVICE_KEY` if missing,
shared by the API and Python service, without changing the Gemini key or IAM password.
When launching Compose directly, set a dedicated service key of at least 24 characters.
The Python service runs non-root, from a read-only source mount, with no published port,
pip packages or persistent chat store. Missing credentials produces an unavailable response.

The API enforces Farmer/Admin login, 1–2000-character questions, 16 KiB request bodies,
six questions/user/minute and two simultaneous upstream requests per API instance. The
rate-limit map has at most 1,024 active user windows. Limits are process-local, reset on
restart, and are not distributed quotas. Python permits two simultaneous model calls.
The API uses bounded 32 KiB response reads and connect/read timeouts.

The browser warns about Google, displays loading/errors, allows only approved source URLs,
and retains at most ten exchanges in page memory. Navigation/sign-out clears chat. Answers
are `no-store`, excluded from the service-worker cache and never persisted to browser storage,
MongoDB or application traces. Each question is independent. Cancelling a browser wait does
not guarantee cancellation of an already-sent cloud request or its charge.

## Verification and remaining work

```bash
# Repository root; offline providers and isolated loopback HTTP fixtures only:
python3 -m unittest discover -s iot/ai/service/tests -v
```

CI uses scripted provider replies, baseline checks and isolated HTTP tests, never a Gemini
key. Hosting browser CI tests authentication, unavailable-service messages and scripted
answer/source rendering (including HTML-as-text), not a live cloud browser session.
Broader factual/language evaluations, local model runs, read-only MCP tools and complete
LLMOps remain future work. The assistant is not automatically promoted based on one score.

Sources: [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output),
[generateContent](https://ai.google.dev/api/generate-content), [Ollama chat](https://docs.ollama.com/api/chat),
[structured output](https://docs.ollama.com/capabilities/structured-outputs),
[model list](https://docs.ollama.com/api/tags). Agronomic sources are stored per corpus note.

OpenAI Codex assisted Aziz Karray with corpus summaries, adapters, citations, context-based
answers, API/service/PWA integration, evaluation, tests and documentation. The root attribution
prompt journal remains a separate team follow-up.
