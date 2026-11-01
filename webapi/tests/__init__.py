"""Test package. The environment is set here, before any test module imports webapi.app, so every test file
(also when run on its own) uses a temporary data folder and never the live webapi_data/ database."""
import json
import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
os.environ.setdefault("RL_WEB_DATA", tempfile.mkdtemp(prefix="rl-web-test-"))
os.environ.setdefault("RL_CLAUDE_CMD", json.dumps([sys.executable, str(_HERE / "fake_claude.py")]))
os.environ.setdefault("RL_EXECUTOR", "cli")
os.environ.setdefault("RL_PAPER_AUTOPILOT", "0")  # stage tests step manually; test_autopilot.py turns it on
os.environ.setdefault("RL_LOOP_TICKER", "0")      # tests advance loops explicitly (GET /loops/{id} reconciles)
