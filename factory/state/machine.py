"""Durable, monotonic project state with hash-linked transition history."""
import datetime
import hashlib
import json
import pathlib

from factory.io import atomic_json


STATES = ["INITIALIZED", "IDEA_READY", "PAPER_READY", "REVIEWED", "CODE_RUN", "REFINED"]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class ProjectState:
    def __init__(self, project_id, state="INITIALIZED", blocked_reason="", history=None):
        self.project_id = project_id
        self.state = state
        self.blocked_reason = blocked_reason
        self.history = history or []

    def to_dict(self):
        return {"schema_version": 1, "project_id": self.project_id, "state": self.state,
                "blocked_reason": self.blocked_reason, "history": self.history}

    @classmethod
    def load(cls, path):
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return cls(value["project_id"], value["state"], value.get("blocked_reason", ""),
                   value.get("history", []))

    def save(self, path):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(path, self.to_dict())


def transition(state, target, gate, input_hashes=None, output_hashes=None):
    if target not in STATES:
        raise ValueError(f"unknown target state: {target}")
    current_index, target_index = STATES.index(state.state), STATES.index(target)
    if target_index != current_index + 1:
        raise ValueError(f"non-sequential transition {state.state} -> {target}")
    if gate.get("verdict") != "PASS":
        state.blocked_reason = gate.get("reason", "gate did not pass")
        return state
    previous = state.history[-1]["event_hash"] if state.history else "GENESIS"
    event = {"at": now(), "from": state.state, "to": target,
             "gate": gate, "input_hashes": input_hashes or {},
             "output_hashes": output_hashes or {}, "previous_event_hash": previous}
    event["event_hash"] = hashlib.sha256(canonical(event).encode()).hexdigest()
    state.history.append(event)
    state.state, state.blocked_reason = target, ""
    return state
