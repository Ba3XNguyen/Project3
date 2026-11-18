"""Deterministic, standard-library ASSIST2009 event preparation. Never trains."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import sys

from adapters import iter_chunks, sequence_row

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name("config.json")
MISSING = {"", "nan", "na", "null", "none"}
EVENT_FIELDS = ["event_id", "source_record", "user_id", "order_id", "problem_id", "skill_id",
                "correct", "original", "split", "skill_idx", "model_position", "common_target", "target_reason"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_users(events, config):
    users = sorted({e["user_id"] for e in events})
    random.Random(config["seed"]).shuffle(users)
    ntrain = int(len(users) * config["train_fraction"])
    nvalid = int(len(users) * config["validation_fraction"])
    return {u: split for split, group in (
        ("train", users[:ntrain]), ("validation", users[ntrain:ntrain+nvalid]),
        ("test", users[ntrain+nvalid:])) for u in group}


def fit_skill_mapping(events):
    """IDs alone from train; no validation/test labels or catalog are used."""
    skills = sorted({e["skill_id"] for e in events if e["split"] == "train"}, key=int)
    return {skill: idx for idx, skill in enumerate(skills)}


def assign_eligibility(events, mapping):
    positions = Counter()
    for event in events:
        event["skill_idx"] = mapping.get(event["skill_id"])
        if event["skill_idx"] is None:
            event.update(model_position=-1, common_target=0, target_reason="oov_skill")
        else:
            pos = positions[event["user_id"]]
            event.update(model_position=pos, common_target=int(pos > 0),
                         target_reason="eligible" if pos else "first_known_interaction")
            positions[event["user_id"]] += 1
    return events


def load_pilot(raw, encoding):
    stages = ["required_keys", "binary_correct", "nonmissing_skill", "valid_skill_format",
              "single_skill", "original_main"]
    passed, exceptions, raw_skills = Counter(), Counter(), set()
    events, excluded, raw_ids, raw_pairs = [], [], set(), Counter()
    prev_user_order, raw_order_decreases = {}, 0
    with Path(raw).open(newline="", encoding=encoding, errors="strict") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        for record, row in enumerate(reader, 1):
            passed["raw"] += 1
            order, user, problem = (row[k].strip() for k in ("order_id", "user_id", "problem_id"))
            correct, skill, original = (row[k].strip() for k in ("correct", "skill_id", "original"))
            numeric_keys = all(re.fullmatch(r"\d+", x) for x in (order, user, problem))
            if numeric_keys:
                oid, uid, pid = int(order), int(user), int(problem)
                if oid in raw_ids:
                    raise ValueError("Duplicate raw order_id: ambiguous event; stop rather than deduplicate")
                raw_ids.add(oid)
                raw_pairs[uid, pid] += 1
                if uid in prev_user_order and oid < prev_user_order[uid]:
                    raw_order_decreases += 1
                prev_user_order[uid] = oid
            if skill.lower() not in MISSING:
                raw_skills.add(skill)
            attempt, hint, response_time = (float(row[k]) for k in ("attempt_count", "hint_count", "ms_first_response"))
            flags = {"correct1_attempt_not1": correct == "1" and attempt != 1,
                     "correct1_attempt0": correct == "1" and attempt == 0,
                     "correct1_hint_positive": correct == "1" and hint > 0,
                     "attempt_zero": attempt == 0, "attempt_gt1": attempt > 1,
                     "hint_positive": hint > 0, "response_time_negative": response_time < 0,
                     "response_time_zero": response_time == 0}
            exceptions.update(k for k, v in flags.items() if v)
            checks = [numeric_keys, correct in {"0", "1"}, skill.lower() not in MISSING,
                      re.fullmatch(r"\d+(?:_\d+)*", skill) is not None,
                      re.fullmatch(r"\d+", skill) is not None, original == "1"]
            reason = None
            for stage, keep in zip(stages, checks):
                if not keep:
                    reason = stage
                    break
                passed[stage] += 1
            if reason:
                excluded.append({"source_record": record, "order_id": order, "user_id": user, "reason": reason})
            else:
                events.append({"event_id": f"assist2009:{oid}", "source_record": record,
                               "user_id": uid, "order_id": oid, "problem_id": pid, "skill_id": skill,
                               "correct": int(correct), "original": 1})
    events.sort(key=lambda e: (e["user_id"], e["order_id"]))
    quality = []
    before = passed["raw"]
    for stage in stages:
        after = passed[stage]
        quality.append({"stage": stage, "before": before, "after": after, "removed": before - after,
                        "removed_fraction_of_previous": (before-after)/before if before else 0,
                        "removed_fraction_of_raw": (before-after)/passed["raw"]})
        before = after
    pilot_flags = Counter()
    # Retained event IDs/records allow anomaly audit without making those fields predictors.
    selected_records = {e["source_record"] for e in events}
    with Path(raw).open(newline="", encoding=encoding) as stream:
        for record, row in enumerate(csv.DictReader(stream), 1):
            if record not in selected_records:
                continue
            if row["correct"] == "1" and float(row["attempt_count"]) != 1:
                pilot_flags["correct1_attempt_not1"] += 1
            if row["correct"] == "1" and float(row["hint_count"]) > 0:
                pilot_flags["correct1_hint_positive"] += 1
    pair_counts = Counter((e["user_id"], e["problem_id"]) for e in events)
    audit = {"raw_rows": passed["raw"], "raw_columns": columns, "filter_steps": quality,
             "raw_exceptions": dict(exceptions), "retained_exceptions": dict(pilot_flags),
             "raw_skill_strings": len(raw_skills),
             "raw_atomic_skills": len({s for skill in raw_skills for s in skill.split("_")}),
             "raw_order_decreases_within_user": raw_order_decreases,
             "raw_repeated_user_problem_extra_events": sum(n-1 for n in raw_pairs.values()),
             "retained_repeated_user_problem_extra_events": sum(n-1 for n in pair_counts.values()),
             "valid_events": len(events), "users": len({e["user_id"] for e in events}),
             "skills": len({e["skill_id"] for e in events}),
             "predictor_allowlist": ["past_skill_idx", "past_correct", "target_skill_idx"],
             "behavioral_fields_exported_to_models": False}
    return events, excluded, audit


def build(output, config_path=DEFAULT_CONFIG):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "dataset_manifest.json").exists():
        raise FileExistsError("Refusing to overwrite a completed preparation output")
    config = json.loads(Path(config_path).read_text())
    assert config["training_authorized"] is False
    raw = ROOT / config["input"]
    digest = sha(raw)
    if digest != config["expected_sha256"]:
        raise ValueError("Raw SHA-256 does not match approved dataset")
    raw_bytes = raw.read_bytes()
    encoding_checks = {}
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            decoded = raw_bytes.decode(encoding, errors="strict")
            encoding_checks[encoding] = {"strict_decode": True, "roundtrip": decoded.encode(encoding) == raw_bytes,
                                         "c1_controls": sum(128 <= ord(c) <= 159 for c in decoded)}
        except UnicodeError as error:
            encoding_checks[encoding] = {"strict_decode": False, "error": str(error)}
    del raw_bytes
    events, excluded, audit = load_pilot(raw, config["encoding"])
    users = split_users(events, config)
    for event in events:
        event["split"] = users[event["user_id"]]
    mapping = fit_skill_mapping(events)
    assign_eligibility(events, mapping)
    dump(output / "resolved_config.json", config)
    dump(output / "skill_mapping.json", {"fitted_on": "train", "skill_to_idx": mapping,
         "idx_to_skill": {str(v): k for k, v in mapping.items()}, "num_c": len(mapping),
         "unknown_id": None, "oov_policy": config["oov"], "metadata_catalog_exception": False})
    dump(output / "split_manifest.json", {"seed": config["seed"], "method": "sort_numeric_users_then_python_Random_shuffle",
         "rounding": "floor(0.70*N), floor(0.15*N), test=remainder", "user_ids_are_keys_not_predictors": True,
         "users": {s: sorted(u for u, split in users.items() if split == s) for s in ("train", "validation", "test")}})
    write_csv(output / "events.csv", EVENT_FIELDS, events)
    write_csv(output / "excluded_events.csv", ["source_record", "order_id", "user_id", "reason"], excluded)
    write_csv(output / "target_eligibility.csv", EVENT_FIELDS, events)
    write_csv(output / "filter_counts.csv", list(audit["filter_steps"][0]), audit["filter_steps"])
    grouped = defaultdict(list)
    for event in events:
        if event["skill_idx"] is not None:
            grouped[event["user_id"]].append(event)
    summary = {}
    for split in ("train", "validation", "test"):
        folder = output / split
        folder.mkdir(exist_ok=True)
        split_events = [e for e in events if e["split"] == split]
        known = [e for e in split_events if e["skill_idx"] is not None]
        write_csv(folder / "pybkt.csv", ["event_id", "user_id", "order_id", "skill_id", "correct", "original"], known)
        sequences, known_users = [], sorted({e["user_id"] for e in known})
        with (folder / "histories.jsonl").open("w") as stream:
            for uid in known_users:
                history = grouped[uid]
                stream.write(json.dumps({"uid": uid, "events": history}, separators=(",", ":")) + "\n")
                for chunk_id, start, chunk in iter_chunks(history, config["sequence_length"]):
                    sequences.append(sequence_row(chunk, chunk_id, start, split, config["sequence_length"]))
        fields = ["fold", "uid", "concepts", "responses", "selectmasks", "event_ids", "chunk_id", "start_model_position"]
        write_csv(folder / "dkt_sequences.csv", fields, sequences)
        skill_counts = Counter(e["skill_id"] for e in known)
        summary[split] = {"users": sum(s == split for s in users.values()), "events": len(split_events),
                          "known_events": len(known), "common_targets": sum(e["common_target"] for e in split_events),
                          "first_known_excluded": sum(e["target_reason"] == "first_known_interaction" for e in split_events),
                          "oov_events": len(split_events)-len(known), "oov_skills": sorted({e["skill_id"] for e in split_events if e["skill_idx"] is None}, key=int),
                          "skills": len({e["skill_id"] for e in split_events}), "dkt_chunks": len(sequences),
                          "singleton_known_users": sum(len(grouped[u]) == 1 for u in known_users),
                          "users_without_known_history": sum(s == split and u not in grouped for u, s in users.items()),
                          "labels": dict(Counter(e["correct"] for e in split_events)),
                          "common_target_labels": dict(Counter(e["correct"] for e in split_events if e["common_target"])),
                          "min_train_events_per_skill" if split == "train" else "min_known_events_per_skill": min(skill_counts.values()),
                          "skills_under_10_events": sum(n < 10 for n in skill_counts.values())}
    audit["encoding_checks"] = encoding_checks
    audit["split_summary"] = summary
    audit["total_common_targets"] = sum(v["common_targets"] for v in summary.values())
    dump(output / "data_quality.json", audit)
    protocol = {"status": "PREPARED_NOT_TRAINED", "target": "supplied binary correct", "unit": "original event_id",
                "common_target_rule": "train-known skill and model_position >= 1; all splits use same rule",
                "first_interaction": config["first_interaction"], "oov": config["oov"],
                "context": config["context"], "validation_test_feedback": "past observed labels only; never refit on heldout",
                "chunking": {"length": config["sequence_length"], "stored_event_overlap": 1,
                             "carry_state_between_same_user_chunks": True, "reset_at_user_boundary": True,
                             "default_upstream_stateless_train_evaluate_compatible": False,
                             "training_loop_stateful_TBPTT_required_in_phase2b": True},
                "pybkt_defaults": {"skill_name": "skill_id", "order_id": "order_id", "user_id": "user_id", "correct": "correct"},
                "bkt": {"backend_data_adapter": "source-py", "variant": "standard_no_forgetting", "multiprior": False,
                        "predict_before_update": True, "common_mask_first_user_event_only": True,
                        "first_encounter_of_new_skill_after_other_events": "eligible via skill prior"},
                "baseline": "train-only per-skill frequency, fixed during validation/test; not fitted in Phase 2A",
                "metrics": ["ROC_AUC", "Accuracy_at_0.5", "LogLoss", "Brier"],
                "metric_policy": "micro pooled exact event_id set per split; one-class AUC=undefined, never fabricated; logloss clip epsilon=1e-7 for all models",
                "prediction_contract": ["event_id", "probability"], "target_join_must_be_exact": True,
                "training_implemented": False}
    dump(output / "evaluation_protocol.json", protocol)
    assert sha(raw) == digest
    files = {str(p.relative_to(output)): {"bytes": p.stat().st_size, "sha256": sha(p)}
             for p in sorted(output.rglob("*")) if p.is_file() and "reference" not in p.relative_to(output).parts
             and p.name not in {"dataset_manifest.json", "prepare.log", "integrity_before.json"}}
    manifest = {"raw": {"path": config["input"], "sha256": digest, "bytes": raw.stat().st_size},
                "python": platform.python_version(), "config_sha256": sha(config_path), "artifacts": files,
                "valid_events": len(events), "users": len(users), "skills_in_pilot": audit["skills"],
                "train_mapped_skills": len(mapping), "total_common_targets": audit["total_common_targets"],
                "models_trained": [], "phase": "2A"}
    dump(output / "dataset_manifest.json", manifest)
    print(json.dumps({"events": len(events), "users": len(users), "skills": audit["skills"],
                      "common_targets": audit["total_common_targets"], "split_summary": summary}, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/assist2009_phase2a")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    build(args.output, args.config)
