# YOLO run audit and quality checks

This is the first MLOps layer around Amir's existing YOLO training and held-out evaluation.
It checks inputs, preserves the inputs/code used for a run, records versions and produces
a quality decision. It does not add an assistant, deploy a model or replace the Pi's weights.

```text
merged YOLO dataset -> audit -> snapshot + run record -> existing train_yolo.py
                                                         |
                             report <- quality policy <- held-out test metrics
```

## 1. Audit a dataset without training

From the repository root (Linux/macOS; on Windows use `.venv\Scripts\python`):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r iot/ai/model/requirements-mlops.txt
.venv/bin/python iot/ai/model/run_pipeline.py \
  --data database/basil-merged/data.yaml \
  --out iot/ai/model/runs/dataset-audit-001 --audit-only
```

This needs only Pillow and PyYAML. It does not import a neural-network runtime, download
weights, start Docker or change the source dataset. It produces `dataset-audit.json`,
`data.resolved.yaml`, `run.json` and `report.md`. Audit-only does not copy the pictures or
claim anything about model accuracy.

The audit checks:

- train/validation/test directories exist, are distinct and contain images;
- class names/IDs are consistent, and every image has a readable box-label file;
- YOLO box rows have five fields, legal classes, finite normalized coordinates and positive size;
- unreadable pictures, unsupported files, symlinks and orphan label files are rejected;
- identical decoded RGB pictures do not appear across splits, even if file encoding differs;
- SHA-256 fingerprints cover image bytes, label bytes, classes and split membership.

Supported layouts include `train/images` + `train/labels` and `images/train` + `labels/train`,
with a list or consecutive integer mapping of names. This deliberately audits directory-based
datasets, not image-list files, remote URLs or segmentation polygons. Convert polygons with
the existing `merge_yolo_datasets.py` first. Empty label files explicitly represent backgrounds.
Use JPEG, PNG, BMP or WebP images; clean other entries out of the image directories.

The final audit detects exact decoded-pixel duplicates, not all recompressed/rotated photos,
same-session pictures or semantic label errors. Amir's merger already handles perceptual
near-duplicate grouping. Dataset curation and reviewing its `audit.json` remain necessary.

## 2. Choose an explicit policy

`policies/example.json` contains **illustrative engineering values**, not requirements from
the professor, validated disease-detection targets or a claim that our current model passes.
Copy it, choose thresholds before examining the new test results, and version your policy:

```bash
cp iot/ai/model/policies/example.json iot/ai/model/policies/team.json
# Edit the thresholds and version in team.json, then review/commit that policy.
```

Bounds can cover overall and per-class precision, recall, mAP50 and mAP50-95 (numbers from
0 to 1). Minimum test-image counts prevent treating a class with very little evidence as
well evaluated. Missing classes, invalid/nonfinite scores, wrong class counts and policy
typos fail closed. JSON scores keep full precision: display rounding cannot turn a score
just below a threshold into a passing result.

## 3. Run training and evaluation

Only when you intend to train, install the separate YOLO dependencies and provide local
starting weights. This can take significant time and disk space; it is not done by CI.

```bash
.venv/bin/python -m pip install -r iot/ai/model/requirements-yolo.txt
.venv/bin/python iot/ai/model/run_pipeline.py \
  --data database/basil-merged/data.yaml \
  --model /path/to/local/yolo26n.pt \
  --policy iot/ai/model/policies/team.json \
  --out iot/ai/model/runs/basil-detect-0.2 \
  --device cpu --epochs 80 --imgsz 640 --batch 16 --seed 2026
```

Choose `--device 0` for a configured GPU. The wrapper requires local starting weights;
it does not select/download them for you. Training uses Amir's existing script, validation
selects the best epoch, and the held-out test split is explicitly evaluated once at the end.
The MobileNet/TFLite workflow remains separate and unchanged.

For a training run, the pipeline copies images, labels, initial weights and pipeline source
into the new output directory. **Allow extra disk space for that snapshot.** Fresh dataset
paths avoid stale YOLO label caches. Source files and disposable caches are not deleted.
Fingerprints are checked when copying and again after training; changed source or snapshot
inputs invalidate the run. Keep datasets stable while a run is in progress.

Each output directory is new and is never overwritten. Outputs are ignored by Git under
`iot/ai/model/runs/`; keep private/licensed data there, not in a PR or public CI artifact.

```text
<run>/
  run.json                 timestamps, settings/seed, Git state, package versions, hashes
  dataset-audit.json       per-split/class counts, file hashes, duplicate/label findings
  quality-policy.json      policy snapshot chosen before training
  data.resolved.yaml       absolute paths used by the trainer
  dataset/data.yaml        portable dataset configuration, alongside copied splits
  initial.pt               starting weights snapshot
  code/                    exact pipeline/trainer source used for the run
  source-metadata/         merger provenance/licence files, when available
  training.log             trainer output and errors
  training/weights/best.pt  candidate model
  training/test-metrics.*   Amir's held-out JSON and readable Markdown report
  quality-gate.json         decision and reasons
  report.md                run summary and findings
```

Git commit, tracked-dirty state, script hashes and installed package versions are recorded;
snapshots preserve the actual inputs even when the working tree contains edits. Seeds and
settings make comparisons traceable, but do not promise bit-identical GPU results.

## Decisions and exit codes

| Result | Meaning | Exit |
|---|---|---:|
| `audited` | Audit-only checks passed; no model evaluated | 0 |
| `eligible_for_review` | Candidate meets the supplied policy | 0 |
| `dataset_rejected` | Audit failed; training was not started | 2 |
| `rejected` | Evaluation failed the supplied policy | 2 |
| `failed` / input error | Training/runtime failure, changed inputs or invalid configuration | 1 |

Malformed configuration can fail before a run directory is created. Once training starts,
failures are recorded in `run.json` and the report. A passing result is not automatic model
promotion, medical/agronomic validation or proof that the exported NCNN model performs the
same. Pi benchmarking, export evaluation and deployment remain separate work.

## Verification

```bash
.venv/bin/python -m unittest discover -s iot/ai/model/tests -v
```

`model-ci.yml` runs these tests and the actual audit CLI on small artificial images, then
uploads the synthetic audit report. Tests cover invalid labels, leakage, changed inputs,
run records, failed trainers, bad metrics and gate rejection. A fake YOLO adapter verifies
that the existing trainer evaluates `split="test"` once and saves unrounded metrics.
Fabricated metrics/weights in tests exercise software behavior only: CI does not train or
claim to measure a real detector. No production dataset or model quality result is fabricated.

## Sources and assistance

- Existing team scripts: `merge_yolo_datasets.py` and `train_yolo.py` from Amir's PR #11.
- [Ultralytics detection dataset format](https://docs.ultralytics.com/datasets/detect/).
- [Ultralytics validation API and metrics](https://docs.ultralytics.com/modes/val/).
- OpenAI Codex assisted Aziz Karray with the audit, orchestration, quality checks, tests
  and documentation. The team's prompt journal remains a separate follow-up.
