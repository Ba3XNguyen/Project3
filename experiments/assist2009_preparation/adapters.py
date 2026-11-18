"""Event-aligned adapters; no fit, optimizer, checkpoint or training entry point."""
import json


def iter_chunks(events, maxlen=200):
    """Overlapping rows for the ordinary stateless pyKT sequence loader.

    A boundary event is a target in one row and the first input of the next.
    This preserves every target, but the ordinary upstream loader resets its
    LSTM at a row boundary. It is therefore an input adapter, not the final
    fair stateful evaluation implementation.
    """
    if maxlen < 2:
        raise ValueError("maxlen must be >= 2")
    if not events:
        return
    start, chunk_id = 0, 0
    while True:
        chunk = events[start:start + maxlen]
        yield chunk_id, start, chunk
        if start + len(chunk) >= len(events):
            break
        start += maxlen - 1
        chunk_id += 1


def iter_stateful_chunks(events, maxlen=200):
    """Non-overlapping chunks for a future stateful DKT implementation.

    The caller must retain the final prediction from chunk *i* as the target
    for the first event of chunk *i+1*, then feed chunk *i+1* with the returned
    recurrent state. This keeps the full user prefix without duplicating an
    event. No training operation is performed here.
    """
    if maxlen < 1:
        raise ValueError("maxlen must be >= 1")
    for chunk_id, start in enumerate(range(0, len(events), maxlen)):
        yield chunk_id, start, events[start:start + maxlen]


def sequence_row(events, chunk_id, start, split, maxlen):
    pad = maxlen - len(events)
    def pack(key):
        return ",".join([str(e[key]) for e in events] + ["-1"] * pad)
    return {"fold": {"train": 1, "validation": 0, "test": -1}[split],
            "uid": events[0]["user_id"], "concepts": pack("skill_idx"),
            "responses": pack("correct"),
            "selectmasks": ",".join(["1"] * len(events) + ["-1"] * pad),
            "event_ids": ",".join([e["event_id"] for e in events] + ["PAD"] * pad),
            "chunk_id": chunk_id, "start_model_position": start}


def prediction_request(known_history, target):
    """The target response is deliberately absent from prediction inputs."""
    if not known_history:
        raise ValueError("DKT requires a previous known event")
    if any(e["user_id"] != target["user_id"] or e["order_id"] >= target["order_id"]
           or e["event_id"] == target["event_id"] for e in known_history):
        raise ValueError("History must contain strictly earlier events of the same user")
    if target["skill_idx"] is None or any(e["skill_idx"] is None for e in known_history):
        raise ValueError("OOV must be excluded from every model's context and targets")
    return {"target_event_id": target["event_id"], "target_concept": target["skill_idx"],
            "history_event_ids": [e["event_id"] for e in known_history],
            "history_concepts": [e["skill_idx"] for e in known_history],
            "history_responses": [e["correct"] for e in known_history]}


def carry_forward(model, concepts, responses, state=None):
    """Reuse unchanged pyKT DKT layers, exposing hidden/cell state externally.

    Evaluation only. This equals DKT.forward on a full prefix in eval mode.
    Phase 2B must implement/validate its training loop separately; no optimizer
    or backward operation is implemented in this Phase 2A adapter.
    """
    if model.training:
        raise ValueError("Phase 2A carry adapter is evaluation-only")
    if model.emb_type != "qid":
        raise ValueError("Only standard DKT qid is covered")
    import torch
    with torch.no_grad():
        embedded = model.interaction_emb(concepts.long() + model.num_c * responses.long())
        hidden, state = model.lstm_layer(embedded, state)
        output = torch.sigmoid(model.out_layer(model.dropout_layer(hidden)))
    return output, state


def join_common_predictions(target_rows, predictions):
    """Reject missing, duplicated, extra or nonfinite predictions before metrics.

    target_rows MUST first be restricted to exactly one requested split.
    Exported context rows / first events must never be scored by accident.
    """
    import math
    expected = {r["event_id"] for r in target_rows if int(r["common_target"]) == 1}
    actual = {}
    for row in predictions:
        event_id = row["event_id"]
        p = float(row["probability"])
        if event_id in actual or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("Duplicate event or invalid probability")
        actual[event_id] = p
    if set(actual) != expected:
        raise ValueError("Predictions do not match the exact common target set")
    return [{"event_id": r["event_id"], "label": int(r["correct"]), "probability": actual[r["event_id"]]}
            for r in target_rows if r["event_id"] in expected]


def read_histories(path):
    with open(path) as stream:
        for line in stream:
            yield json.loads(line)
