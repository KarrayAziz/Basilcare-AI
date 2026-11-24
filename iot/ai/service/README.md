# Cited knowledge assistant

A read-only command-line foundation for US-17 and initial US-20 tracing/evaluation.
It retrieves curated notes, asks an **explicitly selected Ollama or Gemini model to select relevant passage IDs**,
validates that selection, then returns the original notes with their source links.
The model does not write the final prose, invent citation URLs or call device tools.

This is a constrained first version: **not yet in the Farmer PWA**, with no HTTP/MCP
server, live sensor access or pump control. Those integrations need their own authenticated
API/role tests in later PRs.

## Try the explicit no-model baseline

Python 3.10+ and its standard library are sufficient. From the repository root:

```bash
cd iot/ai/service
python3 -m basilcare_assistant ask "How should I prune basil?" --mode extractive
python3 -m basilcare_assistant evaluate --mode extractive --out runs/baseline-001
```

Extractive mode returns the first lexically retrieved note. It is a software baseline,
**not an LLM**, and cannot reliably decide whether a note answers every nuance of a
question. It is never substituted silently when a model provider fails.

## Use your installed local Ollama model

Install/configure Ollama and choose a model yourself. This code never installs, pulls,
downloads or starts a model/service. Use `ollama list` to check installed models and replace
`YOUR_INSTALLED_MODEL` below. Choose a local model supporting structured JSON; cloud model
tags and non-loopback endpoints are rejected.

```bash
# From iot/ai/service, with Ollama already running on your machine:
python3 -m basilcare_assistant ask "What light does basil prefer?" \
  --model YOUR_INSTALLED_MODEL --trace runs/local-traces.jsonl

python3 -m basilcare_assistant evaluate --model YOUR_INSTALLED_MODEL \
  --out runs/local-model-001
```

Ollama is the default mode. Alternatively set `OLLAMA_MODEL` to the installed name.
`--ollama-url` defaults to `http://127.0.0.1:11434` and accepts loopback HTTP origins only.
`--timeout` is a per-request limit between 1 and 120 seconds (default 60). No external API
key is required. The caller is responsible for running a genuinely local Ollama setup;
this helper does not configure the daemon or install model weights.

The adapter reads `/api/tags` to record the installed model digest, calls `/api/chat` with
`stream=false` and a passage-ID JSON schema, then checks that the model tag/digest stayed
stable. It requests temperature 0, seed 2026 and a small output budget. Seeds do not
guarantee identical results on different runtimes/hardware.

Unknown IDs, extra prose fields, tool calls, incomplete output and changed model versions
cause an error rather than an uncited answer. An empty valid selection means "I don't
know". Missing models produce an explicit failure, not a download. Use `--json` to inspect
the result status and metadata.

## Use Gemini explicitly (external API)

Gemini is opt-in with `--mode gemini`. Ollama remains the default; no request switches
providers automatically. Only the curated **public garden** notes from NC State and
Utah State are indexed in this mode. Project/pump/camera notes are excluded before
retrieval and fingerprinting. The question you type and retrieved garden notes are sent
to Google. Do not include private data in a cloud question. Google/provider retention
and billing rules are separate from our metadata-only local traces.

Set `GEMINI_API_KEY` in your shell environment, or put it in the existing ignored
`deploy/.env` and pass that file explicitly. The environment takes precedence. The loader
reads only a literal `GEMINI_API_KEY`; it never executes/sources the file, interpolates
shell expressions or loads other secrets. Never paste a real key into code or Git.
No pip package, Docker change or service restart is required for this terminal helper.

```bash
# From iot/ai/service, using the key already saved in deploy/.env:
python3 -m basilcare_assistant ask "How should I prune basil?" --mode gemini \
  --env-file ../../../deploy/.env --json --trace runs/gemini-traces.jsonl

python3 -m basilcare_assistant evaluate --mode gemini \
  --env-file ../../../deploy/.env --out runs/gemini-public-001
```

The default is `gemini-3.1-flash-lite`, overridable with `--model` or `GEMINI_MODEL`.
Availability and quotas depend on your project. `--timeout` also applies here (1–120 seconds).
The fixed HTTPS Google endpoint receives the key in a header, never a URL. Environment
proxies and HTTP redirects are disabled; no automatic retries or model downloads occur.
Gemini uses a JSON passage-ID schema, temperature 0 and a 256-token output limit. The
same application validation rejects invented IDs, duplicate IDs, extra fields, tool calls,
blocked or incomplete replies. Final prose and links still come from our curated notes.

Quota/prepaid-credit exhaustion, invalid keys, access denial, unavailable models and
connection failures produce sanitized errors. They never silently fall back to baseline
answers. Error bodies, credentials and HTTP headers are not logged. A temporary service
error requires a fresh explicit command if you wish to retry.

Gemini evaluation defaults to [`evaluation/public-garden.json`](evaluation/public-garden.json):
eight cases (five garden questions that call the model and three unsupported questions
that abstain locally). It never defaults to the full project/pump suite. Custom `--cases`
files are explicit inputs: review their questions before using a cloud provider. Expected
IDs must belong to the public garden corpus or the run is rejected before any API call.
This is a small regression set, not comprehensive agronomic or safety validation.

Reports record the requested model, provider-returned version, prompt/corpus hashes,
settings, total elapsed time and reported token usage. Gemini exposes a version string,
**not a downloadable weight digest**; an unchanged string is not proof that provider
weights/runtime are immutable. Mixed reported versions, zero model calls and model errors
cannot produce an overall model-evaluation pass. Tests in CI use scripted replies only;
real cloud evaluations are manual and their ignored `runs/` directories are local.

## Corpus and limits

[`corpus/knowledge.json`](corpus/knowledge.json) contains seven short original notes:
garden light, pruning, pests, germination, harvesting and two project-help topics. Every
passage has a stable ID and reference. The summaries are openly licensed; see
[licence and attribution](corpus/LICENSE.md). Upstream articles/images are not relicensed
or copied wholesale. No remote pages are fetched when asking questions.

Retrieval uses a deterministic BM25-style lexical index, not embeddings. Corpus version
and SHA-256 cover the notes and source metadata. Garden soil advice is excluded for
hydroponic pH/EC/reservoir queries; there are no curated hydroponic targets yet.

Current notes and regression questions are English. A valid citation does not guarantee
relevance: a model can still choose an irrelevant note. Review/extend the corpus and
evaluate the actual installed model before claiming broad cultivation-answer quality.
This is not a plant-diagnosis feature.

English capability checks reject action requests, live-data queries and diagnosis requests
before model calls. These are conservative helpers, not a complete natural-language
authorization system. The structural boundary is that **no API/MQTT/device tool exists
here**; network clients are limited to local Ollama or the explicitly selected Google Gemini API. Later MCP work
must preserve the existing API token, role, confirmation and safety checks.

## Initial traces and regression reports

`ask --trace` is optional. An explicitly requested evaluation writes traces in its new
output directory. JSONL includes request ID/status, corpus/prompt version and hash,
retrieved/selected IDs, requested/resolved model and digest, settings, duration and token
counts when available. Gemini traces also record corpus scope and sanitized provider error codes. The helper does **not** store question text, full prompts, answer
text, conversations, authorization tokens or live device data. This describes these helper
files, not provider logging or retention settings.

[`evaluation/cases.json`](evaluation/cases.json) has 15 simple regression questions covering
known topics, insufficient evidence, capability refusals and an instruction-override attempt.
Reports check expected status/IDs and structural citation integrity. Mixed model versions,
unavailable models and invalid outputs cannot pass the run. Existing output directories
are never overwritten; `runs/` is ignored by Git.

`ask` exits 0 for answers/intentional abstentions and 1 for configuration/model/output
errors. `evaluate` exits 0 only if all cases pass consistently, 2 for failed cases, and
1 for input/report errors.

A manual Gemini 3.1 Flash-Lite run passed all eight public cases on November 24, 2026:
five API calls, 925 tokens and about 4.8 seconds. See the [sanitized result and limits](evaluation/results/README.md).
These measurements describe one run, not guaranteed latency or general model quality.

## Verification and remaining work

```bash
# From the repository root; no pip dependencies or model downloads needed:
python3 -m unittest discover -s iot/ai/service/tests -v
```

CI runs software tests and the explicit extractive baseline, then publishes baseline
reports. Both adapters are tested with scripted API responses in CI, **not real neural
models**. Baseline/mock scores must not be presented as actual model quality. Run an
explicit provider evaluation before making that claim. This first PR does not
automatically promote or deploy an assistant.

Next stages: actual local-model evaluation, broader model evaluations, authenticated API/PWA integration, read-only
MCP tools and broader LLMOps checks. US-17/US-20 are only partially implemented;
US-18/US-19 and complete LLMOps remain unfinished.

## Sources and assistance

- Agronomic/project references are recorded per source in the corpus.
- Ollama: [chat](https://docs.ollama.com/api/chat),
  [structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
  [local model list](https://docs.ollama.com/api/tags).
- Gemini: [structured output](https://ai.google.dev/gemini-api/docs/structured-output),
  [generateContent](https://ai.google.dev/api/generate-content).
- OpenAI Codex assisted Aziz Karray with Gemini support, public-only cloud evaluation,
  sanitized errors and protocol tests, as well as corpus summaries, retrieval, the local adapter,
  citations, metadata traces, tests and documentation. The attribution prompt journal
  remains a separate team follow-up.
