"""A manual generate-validate-repair loop over the Codex/Claude CLIs.

No API keys. Both CLIs carry the user's own subscription session, so model work
happens under an OAuth login rather than a provider secret injected into the
process -- which also means no adapter needs to be trusted with a credential.

Why a manual loop rather than one shot: a single call that returns malformed or
incomplete output is the normal case, not the exception, and the usual response
is to retry the identical prompt and hope. This loop instead feeds the *specific*
validation failure back as the next turn, so attempt two is answering a narrower
question than attempt one. Each turn is recorded with the hash of what went out
and what came back, so a generated artifact can be traced to the exchange that
produced it.

Three properties the rest of the factory depends on:

  Bounded.    A turn budget and a wall-clock budget, both enforced here. A loop
              that can run forever is a loop that will.

  Validated.  The caller supplies a validator, not just a schema. Structural
              validity is table stakes; "did it actually give me forty distinct
              ideas" is the check that matters and only the caller can write it.

  Replayable. `provider="replay"` serves recorded responses from disk, so every
              adapter built on this is testable offline, in CI, with no model and
              no network. Output from a replay run is marked as such and must
              never be presented as a live result.
"""
import datetime
import hashlib
import json
import pathlib
import shutil
import subprocess
import time


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def digest(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class AgentUnavailable(RuntimeError):
    """The CLI is missing or not logged in. Distinct from the model failing."""


class LoopExhausted(RuntimeError):
    """Every attempt was made and none produced output the validator accepted."""

    def __init__(self, message, transcript):
        super().__init__(message)
        self.transcript = transcript


class AgentLoop:
    PROVIDERS = ("claude", "codex", "replay")

    def __init__(self, provider="claude", model=None, max_turns=4,
                 budget_seconds=1800, replay_dir=None, workdir=None):
        if provider not in self.PROVIDERS:
            raise ValueError(f"provider must be one of {self.PROVIDERS}")
        self.provider = provider
        self.model = model
        self.max_turns = int(max_turns)
        self.budget_seconds = float(budget_seconds)
        self.replay_dir = pathlib.Path(replay_dir) if replay_dir else None
        self.workdir = pathlib.Path(workdir).resolve() if workdir else None
        self.executable = None if provider == "replay" else shutil.which(provider)

    # -- health -------------------------------------------------------------

    def healthcheck(self):
        """Report availability and login separately -- they fail for different reasons.

        The previous check looked for the substring '"loggedIn": true' in combined
        output. That is right by accident: it also matches a line saying the user
        is not logged in if the JSON is formatted differently. Parse it instead.
        """
        if self.provider == "replay":
            available = bool(self.replay_dir and self.replay_dir.is_dir())
            return {"status": "PASS" if available else "BLOCK", "provider": "replay",
                    "authentication": "not applicable (recorded responses)",
                    "detail": str(self.replay_dir) if available else "no replay directory"}
        if not self.executable:
            return {"status": "BLOCK", "provider": self.provider,
                    "reason": "CLI_NOT_INSTALLED",
                    "detail": f"{self.provider} is not on PATH",
                    "remedy": (f"install the {self.provider} CLI, then log in with "
                               f"`{self.provider} "
                               f"{'login' if self.provider == 'codex' else '/login'}`")}
        command = ([self.executable, "login", "status"] if self.provider == "codex"
                   else [self.executable, "auth", "status"])
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", shell=False,
                                       timeout=60)
        except (subprocess.SubprocessError, OSError) as exc:
            return {"status": "BLOCK", "provider": self.provider,
                    "reason": "CLI_ERROR", "detail": str(exc)}
        text = (completed.stdout or "") + (completed.stderr or "")
        logged_in = False
        try:
            payload = json.loads(completed.stdout)
            logged_in = bool(payload.get("loggedIn"))
            method = payload.get("authMethod", "unknown")
        except (json.JSONDecodeError, AttributeError):
            logged_in = "Logged in" in text
            method = "subscription/oauth" if logged_in else "none"
        if not logged_in:
            return {"status": "BLOCK", "provider": self.provider,
                    "reason": "NOT_LOGGED_IN", "executable": self.executable,
                    "authentication": method,
                    "detail": f"{self.provider} CLI is installed but not authenticated",
                    "remedy": (f"run `{self.provider} "
                               f"{'login' if self.provider == 'codex' else '/login'}` "
                               f"once; no API key is required")}
        return {"status": "PASS", "provider": self.provider, "executable": self.executable,
                "authentication": method or "subscription/oauth"}

    # -- one turn -----------------------------------------------------------

    def _replay(self, index):
        candidates = sorted(self.replay_dir.glob("turn-*.json")) if self.replay_dir else []
        if index >= len(candidates):
            raise AgentUnavailable(
                f"replay directory has {len(candidates)} turns; turn {index + 1} requested")
        return candidates[index].read_text(encoding="utf-8")

    def _invoke(self, prompt, schema_path, turn_index):
        if self.provider == "replay":
            return self._replay(turn_index), {"replayed": True}
        if not self.executable:
            raise AgentUnavailable(f"{self.provider} CLI is not installed")
        if self.provider == "claude":
            command = [self.executable, "-p", "--output-format", "json",
                       "--no-session-persistence", "--permission-mode", "plan",
                       "--disallowedTools", "Bash", "Edit", "Write"]
            if schema_path:
                command += ["--json-schema", str(schema_path)]
            if self.model:
                command += ["--model", self.model]
            # The prompt goes on stdin: a whole manuscript does not fit in a
            # Windows command line (about 32k characters).
            stdin_text = prompt
        else:
            command = [self.executable, "exec", "--sandbox", "read-only", "--ephemeral",
                       "--skip-git-repo-check"]
            if schema_path:
                command += ["--output-schema", str(schema_path)]
            if self.workdir:
                command += ["-C", str(self.workdir)]
            command.append(prompt)
            stdin_text = None
        completed = subprocess.run(
            command, input=stdin_text, capture_output=True, text=True, encoding="utf-8",
            errors="replace", shell=False, timeout=self.budget_seconds,
            cwd=str(self.workdir) if self.workdir else None)
        if completed.returncode != 0:
            raise AgentUnavailable(
                f"{self.provider} CLI exited {completed.returncode}: "
                f"{(completed.stderr or completed.stdout)[:400]}")
        return completed.stdout, {"returncode": completed.returncode}

    @staticmethod
    def _unwrap(raw):
        """Both CLIs wrap the answer; dig the payload out without guessing wildly."""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(payload, dict):
            for key in ("structured_output", "result", "output", "last_message"):
                if key in payload:
                    inner = payload[key]
                    if isinstance(inner, str):
                        try:
                            return json.loads(inner)
                        except json.JSONDecodeError:
                            return inner
                    return inner
        return payload

    # -- the loop -----------------------------------------------------------

    def run(self, prompt, validator, schema_path=None, repair_hint=""):
        """Generate, validate, and on failure ask again with the specific complaint.

        `validator(payload) -> list[str]` returns the problems it found; an empty
        list accepts. Returning a reason rather than a boolean is what makes the
        next turn worth taking.
        """
        started = time.monotonic()
        transcript, current = [], prompt
        for turn in range(self.max_turns):
            elapsed = time.monotonic() - started
            if elapsed > self.budget_seconds:
                raise LoopExhausted(
                    f"budget of {self.budget_seconds}s exhausted after {turn} turn(s)",
                    transcript)
            raw, meta = self._invoke(current, schema_path, turn)
            payload = self._unwrap(raw)
            problems = []
            if payload is None or isinstance(payload, str):
                problems = ["response was not JSON matching the requested schema"]
            else:
                try:
                    problems = list(validator(payload)) or []
                except Exception as exc:  # a validator bug must not read as model failure
                    raise RuntimeError(f"validator raised {type(exc).__name__}: {exc}") from exc
            transcript.append({
                "turn": turn + 1, "at": now(),
                "prompt_sha256": digest(current), "prompt_chars": len(current),
                "response_sha256": digest(raw), "response_chars": len(raw),
                "problems": problems, "accepted": not problems,
                "seconds": round(time.monotonic() - started, 3), **meta})
            if not problems:
                return {"status": "PASS", "payload": payload, "turns": turn + 1,
                        "transcript": transcript, "provider": self.provider,
                        "replayed": self.provider == "replay"}
            current = (
                f"{prompt}\n\n---\nYour previous response was rejected. Fix exactly "
                f"these problems and return the corrected JSON only:\n"
                + "\n".join(f"- {problem}" for problem in problems)
                + (f"\n\n{repair_hint}" if repair_hint else ""))
        raise LoopExhausted(
            f"{self.max_turns} turns did not produce output the validator accepted; "
            f"last problems: {transcript[-1]['problems'] if transcript else 'none'}",
            transcript)

    def provenance(self, result):
        """A receipt binding the artifact to the exchange that produced it."""
        return {"schema_version": 1, "backend": self.provider, "model": self.model or "default",
                "authentication": "subscription/oauth" if self.provider != "replay"
                                  else "recorded responses",
                "turns": result["turns"], "transcript": result["transcript"],
                "replayed": result.get("replayed", False),
                "trust": "REPLAYED_FIXTURE" if result.get("replayed") else "LIVE_MODEL_OUTPUT",
                "recorded_at": now()}
