import json
from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataset_audit import audit_dataset, read_config, sha256
from quality_gate import assess, validate_policy
import run_pipeline
import train_yolo
from fixtures import dataset, metrics, NAMES, POLICY


class DatasetFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = dataset(self.root / "dataset")


class DatasetTest(DatasetFixture):
    def test_fingerprint_is_portable_and_content_sensitive(self):
        first = audit_dataset(self.data)
        copied = self.root / "copied"
        shutil.copytree(self.data.parent, copied)
        self.assertTrue(first["ok"])
        self.assertEqual(first["fingerprint"], audit_dataset(copied / "data.yaml")["fingerprint"])
        (copied / "train/labels/0.txt").write_text("0 0.5 0.5 0.2 0.2\n")
        self.assertNotEqual(first["fingerprint"], audit_dataset(copied / "data.yaml")["fingerprint"])

    def test_duplicate_pixels_detected_across_encodings_and_splits(self):
        with Image.open(self.data.parent / "train/images/0.png") as picture:
            picture.save(self.data.parent / "test/images/0.png", compress_level=0)
        audit = audit_dataset(self.data)
        self.assertFalse(audit["ok"])
        self.assertTrue(any("cross-split duplicate" in e for e in audit["errors"]))

    def test_label_validation_and_orphans(self):
        label = self.data.parent / "train/labels/0.txt"
        for contents in ("5 .5 .5 .2 .2", "0 nan .5 .2 .2", "0 .5 .5 0 .2",
                         "0 .5 .5 1.1 .2", "0 .1 .1 .2 .2 .3 .3", "bad .5 .5 .2 .2"):
            with self.subTest(contents=contents):
                label.write_text(contents)
                self.assertFalse(audit_dataset(self.data)["ok"])
        label.unlink()
        self.assertIn("missing label", " ".join(audit_dataset(self.data)["errors"]))
        label.write_text("")  # Explicit background annotation is allowed.
        self.assertTrue(audit_dataset(self.data)["ok"])
        (label.parent / "orphan.txt").write_text("")
        self.assertIn("label without image", " ".join(audit_dataset(self.data)["errors"]))

    def test_unreadable_or_empty_split_is_rejected(self):
        image = self.data.parent / "test/images/0.png"
        image.write_bytes(b"not an image")
        self.assertFalse(audit_dataset(self.data)["ok"])
        for file in image.parent.iterdir():
            file.unlink()
        self.assertIn("no images", " ".join(audit_dataset(self.data)["errors"]))

    def test_config_requires_real_separate_splits_and_unique_names(self):
        original = yaml.safe_load(self.data.read_text())
        for modification in ({"names": ["same", "same"]}, {"names": {1: "wrong"}},
                             {"test": "train/images"}, {"test": ""}, {"train": ["train/images"]}):
            with self.subTest(modification=modification):
                self.data.write_text(yaml.safe_dump({**original, **modification}))
                with self.assertRaises(ValueError):
                    read_config(self.data)

    def test_standard_images_split_layout_and_unsupported_files(self):
        config = yaml.safe_load(self.data.read_text())
        for split, old in (("train", "train"), ("val", "valid"), ("test", "test")):
            for kind in ("images", "labels"):
                destination = self.data.parent / kind / split
                destination.parent.mkdir(exist_ok=True)
                shutil.move(str(self.data.parent / old / kind), destination)
            config[split] = f"images/{split}"
        self.data.write_text(yaml.safe_dump(config))
        self.assertTrue(audit_dataset(self.data)["ok"])
        self.assertEqual(train_yolo.count_test_instances(self.data, NAMES), ([1, 1], [1, 1]))
        (self.data.parent / "images/train/untracked.tiff").write_bytes(b"unsupported")
        self.assertIn("unsupported", " ".join(audit_dataset(self.data)["errors"]))


class GateTest(DatasetFixture):
    def test_quality_pass_and_low_score_rejection(self):
        audit = audit_dataset(self.data)
        result = metrics(audit)
        self.assertEqual(assess(result, audit, POLICY)["status"], "eligible_for_review")
        result["overall"]["mAP50"] = 0.4996
        gate = assess(result, audit, POLICY)
        self.assertEqual(gate["status"], "rejected")
        self.assertFalse(gate["deployed"])

    def test_missing_nonfinite_or_wrongly_typed_metrics_fail_closed(self):
        audit = audit_dataset(self.data)
        for value in (None, float("nan"), float("inf"), True, -0.1, 1.1):
            with self.subTest(value=value):
                result = metrics(audit)
                result["per_class"]["healthy"]["recall"] = value
                self.assertEqual(assess(result, audit, POLICY)["status"], "rejected")
        for change in ({"classes": NAMES[::-1]}, {"per_class": {}}, {"overall": None}):
            self.assertEqual(assess({**metrics(audit), **change}, audit, POLICY)["status"], "rejected")

    def test_class_support_and_counts_must_match_audit(self):
        audit = audit_dataset(self.data)
        result = metrics(audit)
        result["per_class"]["healthy"]["test_images"] = 99
        self.assertEqual(assess(result, audit, POLICY)["status"], "rejected")
        stricter = {**POLICY, "minimum_test_images_per_class": 10}
        self.assertEqual(assess(metrics(audit), audit, stricter)["status"], "rejected")

    def test_policy_typos_or_invalid_limits_rejected(self):
        for change in ({"minimum_overall": {"map_typo": 0.5}},
                       {"minimum_test_images_per_class": 0}, {"minimum_test_images_per_class": True},
                       {"minimum_per_class": {"recall": float("nan")}}, {"version": ""}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_policy({**POLICY, **change})


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = dataset(self.root / "dataset")
        self.policy = self.root / "policy.json"
        self.policy.write_text(json.dumps(POLICY))
        self.initial = self.root / "initial.pt"
        self.initial.write_bytes(b"software fixture, not neural weights")
        self.args = SimpleNamespace(data=self.data, out=self.root / "run", audit_only=False,
                                    policy=self.policy, model=self.initial, epochs=1, patience=0,
                                    imgsz=32, batch=1, device="cpu", workers=0, seed=2026)

    def fake_training(self, command, **kwargs):
        # Fabricated output exercises orchestration; it does not demonstrate model accuracy.
        run = self.args.out / "training"
        (run / "weights").mkdir(parents=True)
        (run / "weights/best.pt").write_bytes(b"fabricated trained weights")
        result = metrics(audit_dataset(self.data))
        result.update(run="training", data=str(self.args.out / "data.resolved.yaml"),
                      imgsz=self.args.imgsz, epochs_requested=self.args.epochs)
        (run / "test-metrics.json").write_text(json.dumps(result))
        (run / "test-metrics.md").write_text("# Synthetic software-test metrics\n")

    def test_audit_only_cli_does_not_import_or_download_a_model(self):
        result = subprocess.run([sys.executable, str(run_pipeline.HERE / "run_pipeline.py"),
                                 "--data", str(self.data), "--out", str(self.args.out), "--audit-only"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.args.out / "run.json").read_text())
        self.assertEqual(record["status"], "audited")
        self.assertFalse((self.args.out / "training").exists())
        self.assertNotIn("quality", record)

    def test_success_binds_data_settings_policy_and_artifacts(self):
        cache = self.data.parent / "train/labels.cache"
        cache.write_bytes(b"stale cache must not be used")
        (self.data.parent / "SOURCES.md").write_text("Artificial software-test pictures only.\n")
        self.assertEqual(run_pipeline.run(self.args, runner=self.fake_training), 0)
        record = json.loads((self.args.out / "run.json").read_text())
        self.assertEqual(record["status"], "eligible_for_review")
        self.assertEqual(record["settings"]["seed"], 2026)
        self.assertEqual(record["starting_weights"]["sha256"], sha256(self.initial))
        self.assertEqual(record["dataset"]["fingerprint"], audit_dataset(self.data)["fingerprint"])
        self.assertEqual(record["artifacts"]["weights"]["sha256"],
                         sha256(self.args.out / "training/weights/best.pt"))
        self.assertIn("train_yolo.py", record["scripts"])
        self.assertFalse(record["deployed"])
        self.assertEqual(record["dataset"]["snapshot"], "dataset/")
        self.assertFalse((self.args.out / "dataset/train/labels.cache").exists())
        self.assertEqual(cache.read_bytes(), b"stale cache must not be used")
        self.assertTrue((self.args.out / "source-metadata/SOURCES.md").is_file())
        self.assertEqual(audit_dataset(self.args.out / "dataset/data.yaml")["fingerprint"],
                         record["dataset"]["fingerprint"])
        self.assertEqual(sha256(self.args.out / "initial.pt"), record["starting_weights"]["sha256"])
        self.assertEqual(sha256(self.args.out / "code/train_yolo.py"), record["scripts"]["train_yolo.py"])
        with self.assertRaises(ValueError):
            run_pipeline.run(self.args, runner=self.fake_training)

    def test_invalid_data_never_starts_training(self):
        (self.data.parent / "test/labels/0.txt").unlink()
        def forbidden(*args, **kwargs):
            self.fail("training started on an invalid dataset")
        self.assertEqual(run_pipeline.run(self.args, runner=forbidden), 2)
        self.assertEqual(json.loads((self.args.out / "run.json").read_text())["status"], "dataset_rejected")

    def test_training_crash_is_recorded_without_a_quality_pass(self):
        def crash(*args, **kwargs):
            raise subprocess.CalledProcessError(9, args[0])
        self.assertEqual(run_pipeline.run(self.args, runner=crash), 1)
        record = json.loads((self.args.out / "run.json").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertIn("CalledProcessError", record["error"])
        self.assertNotIn("quality", record)

    def test_changed_dataset_or_initial_weights_invalidates_training(self):
        for kind in ("dataset", "weights"):
            with self.subTest(kind=kind):
                self.args.out = self.root / f"run-{kind}"
                def mutate(command, **kwargs):
                    self.fake_training(command, **kwargs)
                    if kind == "dataset":
                        (self.data.parent / "train/labels/0.txt").write_text("0 .5 .5 .2 .2\n")
                    else:
                        self.initial.write_bytes(b"changed")
                self.assertEqual(run_pipeline.run(self.args, runner=mutate), 1)
                record = json.loads((self.args.out / "run.json").read_text())
                self.assertIn("changed during training", record["error"])

    def test_bad_metrics_cannot_reuse_another_runs_results(self):
        def wrong(command, **kwargs):
            self.fake_training(command, **kwargs)
            path = self.args.out / "training/test-metrics.json"
            result = json.loads(path.read_text())
            result["data"] = "another-run/data.yaml"
            path.write_text(json.dumps(result))
        self.assertEqual(run_pipeline.run(self.args, runner=wrong), 1)
        self.assertFalse((self.args.out / "quality-gate.json").exists())

    def test_snapshot_mutation_and_missing_artifacts_fail_closed(self):
        for kind in ("snapshot", "weights"):
            self.args.out = self.root / f"failure-{kind}"
            def broken(command, **kwargs):
                self.fake_training(command, **kwargs)
                if kind == "snapshot":
                    (self.args.out / "dataset/train/labels/0.txt").write_text("0 .5 .5 .2 .2")
                else:
                    (self.args.out / "training/weights/best.pt").unlink()
            with self.subTest(kind=kind):
                self.assertEqual(run_pipeline.run(self.args, runner=broken), 1)
                self.assertEqual(json.loads((self.args.out / "run.json").read_text())["status"], "failed")

    def test_training_requires_explicit_inputs_before_creating_a_run(self):
        for key in ("model", "policy"):
            original = getattr(self.args, key)
            setattr(self.args, key, None)
            with self.subTest(key=key), self.assertRaises(ValueError):
                run_pipeline.run(self.args, runner=self.fake_training)
            self.assertFalse(self.args.out.exists())
            setattr(self.args, key, original)

    def test_gate_rejection_keeps_a_readable_report_and_nonzero_exit(self):
        policy = {**POLICY, "minimum_overall": {"mAP50": 0.9}}
        self.policy.write_text(json.dumps(policy))
        self.assertEqual(run_pipeline.run(self.args, runner=self.fake_training), 2)
        self.assertEqual(json.loads((self.args.out / "quality-gate.json").read_text())["status"], "rejected")
        self.assertIn("overall.mAP50", (self.args.out / "report.md").read_text())


class TrainerIntegrationTest(unittest.TestCase):
    def test_existing_trainer_tests_once_and_keeps_unrounded_metrics(self):
        with tempfile.TemporaryDirectory(prefix="images-in-parent-") as temp:
            root = Path(temp)
            data = dataset(root / "dataset")
            calls = []
            values = SimpleNamespace(mp=0.8, mr=0.7, map50=0.4996, map=0.3,
                                     ap_class_index=[0, 1], class_result=lambda k: (0.8, 0.7, 0.4996, 0.3))
            class FakeModel:
                names = dict(enumerate(NAMES))
                def __init__(self, path):
                    pass
                def train(self, **options):
                    calls.append(("train", options))
                    folder = Path(options["project"]) / options["name"]
                    (folder / "weights").mkdir(parents=True)
                    (folder / "weights/best.pt").write_bytes(b"fixture")
                    self.trainer = SimpleNamespace(save_dir=folder)
                def val(self, **options):
                    calls.append(("val", options))
                    return SimpleNamespace(box=values)
            with patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=FakeModel)}), redirect_stdout(io.StringIO()):
                train_yolo.main(["--data", str(data), "--project", str(root / "runs"),
                                 "--name", "example", "--device", "cpu", "--epochs", "1"])
            self.assertEqual([kind for kind, _ in calls], ["train", "val"])
            self.assertEqual(calls[1][1]["split"], "test")
            result = json.loads((root / "runs/example/test-metrics.json").read_text())
            self.assertEqual(result["overall"]["mAP50"], 0.4996)
            self.assertEqual(result["per_class"]["healthy"]["test_images"], 1)


if __name__ == "__main__":
    unittest.main()
