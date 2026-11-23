# Cited knowledge assistant — first step

A read-only command-line foundation for US-17 and initial US-20 tracing/evaluation.
It retrieves curated notes, asks a **local Ollama model to select relevant passage IDs**,
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
question. It is never substituted silently when Ollama fails.

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
here**; the only network client calls local Ollama tags/chat endpoints. Later MCP work
must preserve the existing API token, role, confirmation and safety checks.

## Initial traces and regression reports

`ask --trace` is optional. An explicitly requested evaluation writes traces in its new
output directory. JSONL includes request ID/status, corpus/prompt version and hash,
retrieved/selected IDs, requested/resolved model and digest, settings, duration and token
counts when available. The helper does **not** store question text, full prompts, answer
text, conversations, authorization tokens or live device data. This describes these helper
files, not Ollama's own logging settings.

[`evaluation/cases.json`](evaluation/cases.json) has 15 simple regression questions covering
known topics, insufficient evidence, capability refusals and an instruction-override attempt.
Reports check expected status/IDs and structural citation integrity. Mixed model versions,
unavailable models and invalid outputs cannot pass the run. Existing output directories
are never overwritten; `runs/` is ignored by Git.

`ask` exits 0 for answers/intentional abstentions and 1 for configuration/model/output
errors. `evaluate` exits 0 only if all cases pass consistently, 2 for failed cases, and
1 for input/report errors.

## Verification and remaining work

```bash
# From the repository root; no pip dependencies or model downloads needed:
python3 -m unittest discover -s iot/ai/service/tests -v
```

CI runs software tests and the explicit extractive baseline, then publishes baseline
reports. The Ollama adapter is tested with scripted API responses, **not a real neural
model**. Baseline/mock scores must not be presented as actual Ollama quality. Run the
evaluation with an installed model before making that claim. This first PR does not
automatically promote or deploy an assistant.

Next stages: actual local-model evaluation, authenticated API/PWA integration, read-only
MCP tools and broader LLMOps checks. US-17/US-20 are only partially implemented;
US-18/US-19 and complete LLMOps remain unfinished.

## Sources and assistance

- Agronomic/project references are recorded per source in the corpus.
- Ollama: [chat](https://docs.ollama.com/api/chat),
  [structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
  [local model list](https://docs.ollama.com/api/tags).
- OpenAI Codex assisted Aziz Karray with corpus summaries, retrieval, the local adapter,
  citations, metadata traces, tests and documentation. The attribution prompt journal
  remains a separate team follow-up.
