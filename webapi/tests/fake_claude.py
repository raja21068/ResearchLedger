"""Scripted stand-in for the Claude Code CLI (stream-json output) used by tests.

Reads the prompt from stdin. Writes manuscript/main.md, then emits the same
event shapes the real CLI produces. A prompt containing FAIL ends in an error
result; one containing SLOW sleeps so cancellation can be tested.
"""
import json
import sys
import time
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()
session = args[args.index("--resume") + 1] if "--resume" in args else "sess-fake-1"


def emit(obj):
    print(json.dumps(obj), flush=True)


emit({"type": "system", "subtype": "init", "session_id": session, "model": "fake", "cwd": str(Path.cwd())})
if "SLOW" in prompt:
    time.sleep(30)
if "[Research Director" in prompt:
    import re
    plan = re.search(r"plan to `([^`]+)`", prompt).group(1)
    Path(plan).parent.mkdir(parents=True, exist_ok=True)
    steps = [{"workflow": "literature_review", "title": "Find prior work", "values": {"topic": "X"}},
             {"workflow": "pipeline_status", "title": "Check pipeline"}]
    if "BADPLAN" in prompt:
        steps = [{"workflow": "protocol_lock", "values": {"confirm": True}}]
    Path(plan).write_text(json.dumps({"goal": "g", "summary": "s", "steps": steps}), encoding="utf-8")
Path("manuscript").mkdir(exist_ok=True)
Path("manuscript/main.md").write_text("# Title\n\n## Introduction\n\nText with **bold**.\n\n- item\n",
                                      encoding="utf-8")
emit({"type": "assistant", "message": {"content": [
    {"type": "text", "text": "Writing the draft."},
    {"type": "tool_use", "id": "td1", "name": "TodoWrite", "input": {"todos": [
        {"content": "Write draft", "status": "in_progress"}, {"content": "Summarize", "status": "pending"}]}},
    {"type": "tool_use", "id": "tu1", "name": "Write", "input": {"file_path": "manuscript/main.md"}}]}})
emit({"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "tu1", "content": "ok"}]}})
failed = "FAIL" in prompt
emit({"type": "result", "subtype": "success", "is_error": failed,
      "result": "Failed on purpose" if failed else f"Done (resumed={'--resume' in args})",
      "total_cost_usd": 0, "duration_ms": 5, "num_turns": 1, "session_id": session})
sys.exit(1 if failed else 0)
