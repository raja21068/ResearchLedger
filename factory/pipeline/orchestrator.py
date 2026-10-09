"""Run the research stages with verified, input-bound checkpoints.

A checkpoint is an acceleration hint, never proof: on resume we verify the
artifact, its digest, the stage's original input signature, and the entire
upstream chain. Any invalid stage invalidates all its dependants.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import time
import traceback

from factory.io import atomic_json
from factory.pipeline import stages as stage_table
from factory.pipeline.lock import exclusive_run
from factory.pipeline.provenance import hash_file, input_signature, output_signature
from factory.state import STATES, ProjectState, transition

CHECKPOINT = "control/checkpoint.json"
RUN_LOG = "control/run_log.jsonl"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def file_digest(path):
    path = pathlib.Path(path)
    return hash_file(path) if path.is_file() and not path.is_symlink() else None


class Orchestrator:
    def __init__(self, project, context=None, retry_budget=1):
        self.project = pathlib.Path(project).resolve()
        self.context = context if context is not None else {}
        if not isinstance(self.context, dict):
            raise ValueError("context.json must contain a JSON object")
        if isinstance(retry_budget, bool) or int(retry_budget) != retry_budget or retry_budget < 0:
            raise ValueError("retry_budget must be a non-negative integer")
        self.retry_budget = int(retry_budget)
        self.state_path = self.project / "state.json"

    def bootstrap(self):
        (self.project / "_inputs").mkdir(parents=True, exist_ok=True)
        if not self.state_path.is_file():
            ProjectState(self.project.name).save(self.state_path)

    def state(self):
        return ProjectState.load(self.state_path)

    def _log(self, record):
        path = self.project / RUN_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"at": now(), **record}, sort_keys=True) + "\n")

    def signature(self, stage_id):
        return input_signature(self.project, stage_id, self.context)

    def run_stage(self, stage):
        source = self.project / "_inputs" / stage["source"] if stage["source"] else None
        if source is not None and not source.is_file():
            return self._result(stage, "BLOCKED", f"missing required input _inputs/{stage['source']}")
        error = "no attempt made"
        for attempt in range(1, self.retry_budget + 2):
            started = time.monotonic()
            try:
                stage["driver"](self.project, str(source) if source else None, self.context)
            except (ValueError, FileNotFoundError, json.JSONDecodeError, KeyError, OSError) as exc:
                error = str(exc)
                if isinstance(exc, ValueError):
                    break
                continue
            except Exception as exc:
                return self._result(stage, "BLOCKED", f"{type(exc).__name__}: {exc}",
                                    traceback=traceback.format_exc())
            valid, detail = stage_table.artifact_valid(self.project, stage["id"])
            if valid and stage["id"] == "S4":
                from factory.integrations.ledger import enabled, verify_run_receipt
                if enabled(self.context):
                    valid, detail = verify_run_receipt(self.project)
            if valid and stage['id'] == 'S5' and self.context.get('science_mode') == 'validation':
                from factory.science.gates import audit as science_audit
                gate = science_audit(self.project, self.context)
                if gate['status'] != 'PASS_AUTOMATED_INTEGRITY_ONLY':
                    valid, detail = False, 'scientific integrity gate no longer passes'
            if valid:
                return self._result(stage, "PASS", detail, attempts=attempt,
                                    seconds=round(time.monotonic() - started, 3))
            error = detail
        return self._result(stage, "BLOCKED", error)

    def _result(self, stage, status, detail, **extra):
        return {"stage": stage["id"], "title": stage["title"], "status": status,
                "artifact": stage["artifact"],
                "artifact_sha256": file_digest(self.project / stage["artifact"])
                if status == "PASS" else None,
                "detail": detail, **extra}

    def advance_state(self, stage, result):
        historical = self.state()
        for target in stage["states"]:
            if STATES.index(target) <= STATES.index(historical.state):
                continue  # historic events are retained; effective state uses verified checkpoints
            transition(historical, target,
                       {"verdict": "PASS", "stage": stage["id"], "detail": result["detail"]},
                       output_hashes={stage["artifact"]: result["artifact_sha256"] or ""})
        historical.save(self.state_path)
        return historical.state

    def completed(self):
        """Return only a contiguous prefix of verified stage checkpoints."""
        path = self.project / CHECKPOINT
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = {row["stage"]: row for row in payload.get("completed", [])}
        except (OSError, ValueError, KeyError, TypeError):
            return {}
        good = {}
        for stage in stage_table.STAGES:
            stage_id = stage["id"]
            row = rows.get(stage_id)
            if not isinstance(row, dict) or row.get("artifact") != stage["artifact"]:
                break
            try:
                if row.get("input_sha256") != self.signature(stage_id):
                    break
                if row.get("supporting_sha256") != output_signature(self.project, stage_id):
                    break
                valid, _ = stage_table.artifact_valid(self.project, stage_id)
                if valid and stage_id == "S4":
                    from factory.integrations.ledger import enabled, verify_run_receipt
                    if enabled(self.context):
                        valid, _ = verify_run_receipt(self.project)
            except (OSError, ValueError, KeyError, TypeError):
                break
            if valid and stage_id == 'S5' and self.context.get('science_mode') == 'validation':
                from factory.science.gates import audit as science_audit
                valid = science_audit(self.project, self.context)['status'] == 'PASS_AUTOMATED_INTEGRITY_ONLY'
            if not valid or file_digest(self.project / stage["artifact"]) != row.get("artifact_sha256"):
                break
            good[stage_id] = row
        return good

    def effective_state(self, completed=None):
        completed = self.completed() if completed is None else completed
        return STATES[len(completed)]

    def _checkpoint(self, rows):
        path = self.project / CHECKPOINT
        atomic_json(path, {"schema_version": 2, "updated_at": now(),
                           "completed": [rows[s["id"]] for s in stage_table.STAGES
                                         if s["id"] in rows]})

    def run(self, start=None, stop=None, resume=False):
        with exclusive_run(self.project):
            return self._run_locked(start, stop, resume)

    def _run_locked(self, start, stop, resume):
        self.bootstrap()
        selected = stage_table.ordered(start, stop)
        known = self.completed()
        first_idx = stage_table.STAGES.index(selected[0])
        for prerequisite in stage_table.STAGES[:first_idx]:
            if prerequisite["id"] not in known:
                raise ValueError(f"cannot start at {selected[0]['id']}: prerequisite "
                                 f"{prerequisite['id']} is missing or stale; "
                                 "run/resume from that prerequisite first")
        completed = dict(known)
        results, blocked = [], None
        self._log({"event": "RUN_START", "resume": resume,
                   "skipping": sorted(completed) if resume else []})
        for stage in selected:
            stage_id = stage["id"]
            if resume and stage_id in completed:
                results.append({"stage": stage_id, "title": stage["title"],
                                "status": "SKIPPED", "artifact": stage["artifact"],
                                "artifact_sha256": completed[stage_id]["artifact_sha256"],
                                "detail": "input- and artifact-verified checkpoint"})
                continue

            # Rerunning a stage makes every downstream checkpoint untrustworthy,
            # even if the regenerated primary artifact happens to hash identically.
            index = stage_table.STAGES.index(stage)
            for later in stage_table.STAGES[index:]:
                completed.pop(later["id"], None)
            self._checkpoint(completed)
            try:
                before_signature = self.signature(stage_id)
                result = self.run_stage(stage)
                if result["status"] == "PASS" and self.signature(stage_id) != before_signature:
                    result = self._result(stage, "BLOCKED", "stage inputs changed during execution")
            except (OSError, ValueError, TypeError) as exc:
                result = self._result(stage, "BLOCKED", str(exc))
            if result["status"] == "PASS":
                result["historical_state"] = self.advance_state(stage, result)
                completed[stage_id] = {"stage": stage_id, "artifact": stage["artifact"],
                                       "artifact_sha256": result["artifact_sha256"],
                                       "input_sha256": before_signature,
                                       "supporting_sha256": output_signature(self.project, stage_id)}
            results.append(result)
            self._checkpoint(completed)
            self._log({"event": "STAGE", "stage": stage_id, "status": result["status"],
                       "artifact_sha256": result["artifact_sha256"], "detail": result["detail"]})
            if result["status"] != "PASS":
                blocked = {"stage": stage_id, "reason": result["detail"]}
                break

        # Recheck the chain, rather than reporting a historical state after a failure.
        verified = self.completed()
        summary = {"project": str(self.project), "state": self.effective_state(verified),
                   "historical_state": self.state().state,
                   "status": "BLOCKED" if blocked else
                             "COMPLETE" if len(verified) == len(stage_table.STAGES) else "PARTIAL",
                   "stages_complete": len(verified), "stages_total": len(stage_table.STAGES),
                   "blocked": blocked, "stages": results}
        self._log({"event": "RUN_END", "status": summary["status"]})
        return summary
