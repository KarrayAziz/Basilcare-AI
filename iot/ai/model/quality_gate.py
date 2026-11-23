"""Fail-closed quality checks for train_yolo.py's existing held-out metrics schema."""
import math

METRICS = {"precision", "recall", "mAP50", "mAP50_95"}


def score(value):
    return type(value) in (float, int) and math.isfinite(value) and 0 <= value <= 1


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {
        "version", "minimum_overall", "minimum_per_class", "minimum_test_images_per_class"
    }:
        raise ValueError("policy must contain version, minimum_overall, minimum_per_class and minimum_test_images_per_class")
    if not isinstance(policy["version"], str) or not policy["version"].strip():
        raise ValueError("policy needs a version")
    for key in ("minimum_overall", "minimum_per_class"):
        bounds = policy[key]
        if not isinstance(bounds, dict) or not bounds or not set(bounds) <= METRICS:
            raise ValueError(f"{key}: specify supported metrics")
        if any(not score(value) for value in bounds.values()):
            raise ValueError("policy scores must be finite numbers between 0 and 1")
    support = policy["minimum_test_images_per_class"]
    if type(support) is not int or support < 1:
        raise ValueError("minimum_test_images_per_class must be a positive integer")
    return policy


def assess(metrics, audit, policy):
    validate_policy(policy)
    failures = []
    if not isinstance(metrics, dict) or metrics.get("classes") != audit["classes"]:
        return {"status": "rejected", "failures": ["metrics classes do not match audited dataset"],
                "policy_version": policy["version"], "deployed": False}
    if not audit["ok"]:
        failures.append("dataset audit failed")
    overall, per_class = metrics.get("overall", {}), metrics.get("per_class", {})
    if not isinstance(overall, dict) or not isinstance(per_class, dict):
        return {"status": "rejected", "failures": ["overall and per_class must be objects"],
                "policy_version": policy["version"], "deployed": False}
    for name in METRICS:
        if not score(overall.get(name)):
            failures.append(f"overall.{name}: missing or invalid score")
    for name, minimum in policy["minimum_overall"].items():
        value = overall.get(name)
        if score(value) and value < minimum:
            failures.append(f"overall.{name}: {value} < {minimum}")
    for class_name in audit["classes"]:
        result = per_class.get(class_name)
        if not isinstance(result, dict):
            failures.append(f"{class_name}: no held-out class metrics")
            continue
        for metric in METRICS:
            if not score(result.get(metric)):
                failures.append(f"{class_name}.{metric}: missing or invalid score")
        for key, count_key in (("test_images", "images_with"), ("test_boxes", "boxes")):
            expected = audit["splits"]["test"][count_key][class_name]
            if type(result.get(key)) is not int or result[key] != expected:
                failures.append(f"{class_name}.{key}: does not match dataset audit ({expected})")
        support = audit["splits"]["test"]["images_with"][class_name]
        if support < policy["minimum_test_images_per_class"]:
            failures.append(f"{class_name}: only {support} test images; need {policy['minimum_test_images_per_class']}")
        for metric, minimum in policy["minimum_per_class"].items():
            value = result.get(metric)
            if score(value) and value < minimum:
                failures.append(f"{class_name}.{metric}: {value} < {minimum}")
    return {"status": "rejected" if failures else "eligible_for_review", "failures": failures,
            "policy_version": policy["version"], "deployed": False}
