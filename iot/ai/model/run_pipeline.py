"""Audit -> record provenance -> reuse YOLO training/test -> quality gate. Never deploys a model.

An --audit-only run needs only requirements-mlops.txt. Training additionally needs
requirements-yolo.txt, local starting weights, an explicit quality policy and suitable hardware.
"""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import yaml

from dataset_audit import SUFFIXES, audit_dataset, label_directory, resolved_config, sha256
from quality_gate import assess, validate_policy

HERE = Path(__file__).resolve().parent


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def git_state():
    def read(*command):
        try:
            result = subprocess.run(["git", *command], cwd=HERE, capture_output=True, text=True, check=False)
        except OSError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None
    status = read("status", "--porcelain", "--untracked-files=no")
    return {"commit": read("rev-parse", "HEAD"),
            "tracked_worktree_dirty": None if status is None else bool(status)}


def copy_dataset(config, out):
    """Fresh inputs avoid stale Ultralytics label caches and retain the data used by this run."""
    copied = {"names": config["names"], "nc": config["nc"]}
    for split in ("train", "val", "test"):
        images = Path(config[split])
        labels = label_directory(images)
        destination = out / "dataset" / split / "images"
        destination.mkdir(parents=True)
        for image in sorted(images.rglob("*")):
            if image.is_file() and image.suffix.lower() in SUFFIXES:
                relative = image.relative_to(images)
                image_out = destination / relative
                label_out = destination.with_name("labels") / relative.with_suffix(".txt")
                image_out.parent.mkdir(parents=True, exist_ok=True)
                label_out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, image_out)
                shutil.copy2(labels / relative.with_suffix(".txt"), label_out)
        copied[split] = str(destination)
    portable = {"path": ".", "names": config["names"], "nc": config["nc"],
                **{split: f"{split}/images" for split in ("train", "val", "test")}}
    (out / "dataset" / "data.yaml").write_text(yaml.safe_dump(portable, sort_keys=False), encoding="utf-8")
    return copied


def write_report(out, record, audit, gate=None, error=None):
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    if gate is not None:
        record["quality"] = gate
        write_json(out / "quality-gate.json", gate)
    if error:
        record["error"] = error
    write_json(out / "run.json", record)
    lines = [f"# Model run: {out.name}", "", f"Status: **{record['status']}**", "",
             f"Dataset fingerprint: `{audit['fingerprint']}`", "",
             "| Split | Images | Boxes |", "|---|---:|---:|"]
    for split, counts in audit["splits"].items():
        lines.append(f"| {split} | {counts['images']} | {sum(counts['boxes'].values())} |")
    lines += ["", "## Findings", ""]
    findings = audit["errors"] + (gate.get("failures", []) if gate else []) + ([error] if error else [])
    lines += [f"- {item}" for item in findings] or ["- No failures in the checks performed."]
    if gate:
        lines += ["", f"Policy: `{gate.get('policy_version', 'invalid metrics')}`",
                  f"Quality decision: **{gate['status']}**"]
    lines += ["", "No model was deployed. Passing the gate only makes a candidate eligible for review.",
              "Audit-only and fixture tests do not measure a model's accuracy.",
              "See training/test-metrics.md for the held-out evaluation when training completed."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args, runner=subprocess.run):
    out = args.out.resolve()
    if out.exists():
        raise ValueError(f"output already exists; choose a new run directory: {out}")
    audit = audit_dataset(args.data)
    config = resolved_config(args.data)
    if any(out.is_relative_to(Path(config[s]).parent) for s in ("train", "val", "test")):
        raise ValueError("run output must not be inside a dataset split")
    policy = validate_policy(json.loads(args.policy.read_text())) if args.policy else None
    if not args.audit_only and (not args.model or not args.model.is_file() or not policy):
        raise ValueError("training requires local --model weights and an explicit --policy JSON file")
    if not args.audit_only and args.model.stat().st_size == 0:
        raise ValueError("starting weights are empty")
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "dataset-audit.json", audit)
    snapshot = out / "data.resolved.yaml"
    snapshot.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    if policy:
        write_json(out / "quality-policy.json", policy)
    record = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
              "status": "audited" if args.audit_only else "training", "deployed": False,
              "dataset": {"source": str(args.data.resolve()), "fingerprint": audit["fingerprint"],
                          "config_sha256": sha256(args.data)},
              "git": git_state(), "python": platform.python_version(), "platform": platform.platform(),
              "packages": {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()
                           if dist.metadata.get('Name')},
              "scripts": {name: sha256(HERE / name) for name in
                          ("run_pipeline.py", "dataset_audit.py", "quality_gate.py", "train_yolo.py")}}
    record["dataset"]["source_metadata"] = {
        name: sha256(args.data.resolve().parent / name)
        for name in ("SOURCES.md", "manifest.csv", "audit.json")
        if (args.data.resolve().parent / name).is_file()}
    if record["dataset"]["source_metadata"]:
        (out / "source-metadata").mkdir()
        for name in record["dataset"]["source_metadata"]:
            shutil.copy2(args.data.resolve().parent / name, out / "source-metadata" / name)
            record["dataset"]["source_metadata"][name] = sha256(out / "source-metadata" / name)
    if not audit["ok"]:
        record["status"] = "dataset_rejected"
        write_report(out, record, audit)
        return 2
    if args.audit_only:
        write_report(out, record, audit)
        return 0
    settings = {key: getattr(args, key) for key in
                ("epochs", "patience", "imgsz", "batch", "device", "workers", "seed")}
    model_hash = sha256(args.model)
    record.update({"settings": settings,
                   "starting_weights": {"path": str(args.model.resolve()), "sha256": model_hash,
                                        "snapshot": "initial.pt"},
                   "policy_sha256": sha256(out / "quality-policy.json")})
    command = [sys.executable, str(out / "code" / "train_yolo.py"), "--data", str(snapshot),
               "--project", str(out), "--name", "training", "--model", str(out / "initial.pt")]
    for key, value in settings.items():
        command += [f"--{key}", str(value)]
    record["command"] = command
    write_json(out / "run.json", record)
    try:
        (out / "code").mkdir()
        for name, expected_hash in record["scripts"].items():
            shutil.copy2(HERE / name, out / "code" / name)
            if sha256(out / "code" / name) != expected_hash:
                raise ValueError("pipeline code changed while creating this run's snapshot")
        shutil.copy2(args.model, out / "initial.pt")
        if sha256(out / "initial.pt") != model_hash:
            raise ValueError("starting weights changed while creating this run's snapshot")
        snapshot.write_text(yaml.safe_dump(copy_dataset(config, out), sort_keys=False), encoding="utf-8")
        if audit_dataset(snapshot)["fingerprint"] != audit["fingerprint"]:
            raise ValueError("dataset changed while creating this run's snapshot")
        record["dataset"]["snapshot"] = "dataset/"
        write_json(out / "run.json", record)
        with (out / "training.log").open("w", encoding="utf-8") as log:
            runner(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        after = audit_dataset(args.data)
        if not after["ok"] or after["fingerprint"] != audit["fingerprint"]:
            raise ValueError("dataset changed during training; results cannot use the original fingerprint")
        snapshot_after = audit_dataset(snapshot)
        if not snapshot_after["ok"] or snapshot_after["fingerprint"] != audit["fingerprint"]:
            raise ValueError("dataset snapshot changed during training")
        if sha256(args.model) != model_hash:
            raise ValueError("starting weights changed during training")
        if sha256(out / "initial.pt") != model_hash:
            raise ValueError("starting weights snapshot changed during training")
        weights = out / "training" / "weights" / "best.pt"
        metrics_file = out / "training" / "test-metrics.json"
        if not weights.is_file() or weights.stat().st_size == 0:
            raise ValueError("trainer did not produce nonempty best.pt")
        metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        if (metrics.get("run") != "training" or Path(metrics.get("data", "")).resolve() != snapshot
                or metrics.get("imgsz") != args.imgsz or metrics.get("epochs_requested") != args.epochs):
            raise ValueError("held-out metrics do not match this run's data/settings")
        gate = assess(metrics, audit, policy)
        record["artifacts"] = {"weights": {"file": str(weights.relative_to(out)), "sha256": sha256(weights)},
                               "metrics": {"file": str(metrics_file.relative_to(out)), "sha256": sha256(metrics_file)}}
        record["status"] = gate["status"]
        write_report(out, record, audit, gate)
        return 0 if gate["status"] == "eligible_for_review" else 2
    except Exception as error:
        record["status"] = "failed"
        write_report(out, record, audit, error=f"{type(error).__name__}: {error}")
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="new directory; never overwritten")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--model", type=Path, help="local initial .pt weights (not downloaded by this wrapper)")
    parser.add_argument("--policy", type=Path, help="explicit quality policy; the checked-in example is illustrative")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)
    if min(args.epochs, args.imgsz, args.batch) <= 0 or min(args.patience, args.workers) < 0:
        parser.error("epochs, imgsz and batch must be positive; patience and workers nonnegative")
    try:
        result = run(args)
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"Pipeline input error: {error}", file=sys.stderr)
        return 1
    print(f"Report: {args.out.resolve() / 'report.md'}")
    return result


if __name__ == "__main__":
    sys.exit(main())
