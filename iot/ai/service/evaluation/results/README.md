# Manual model evaluation evidence

`gemini-public-2026-11-24.json` records an actual Gemini 3.1 Flash-Lite run using
the public-garden corpus and eight cases in `evaluation/public-garden.json`.
Five requests reached Google; three unsupported questions abstained without a model call.
All eight passed. Google reported 846 input tokens and 79 output tokens (925 total).
The run took about 4.8 seconds, including network time. Temperature was 0 and the
maximum output budget was 256 tokens per call.

This is a single small regression run, not a general quality/safety guarantee. The
reported cloud model version is not a weight digest. API availability, response time,
quota and results may vary. CI does not use a real Gemini key or repeat this paid/quota
consuming run. It tests both protocols offline and checks the no-model baseline.

An initial integration run failed validation of Gemini's documented `thoughtSignature`
text metadata; it also encountered one temporary provider-unavailable response. The
adapter was corrected to accept and discard that opaque metadata, a protocol regression
test was added, and the evaluation was rerun. The snapshot here is that successful run.
The original local runs are preserved under the ignored `runs/` folder.

This snapshot contains case IDs/statuses, versions/hashes, counts, timing and request IDs.
It contains no credentials, raw questions, answer text, provider signatures or HTTP headers.
Questions and curated notes for the five model calls are public gardening material;
project/pump/camera notes were excluded. The full 15-case suite remains separately tested
with the local no-model baseline; this snapshot does not claim a cloud test of that suite.
