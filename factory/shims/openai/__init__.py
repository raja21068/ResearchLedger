"""A stand-in for the `openai` package that answers with the Claude Code CLI.

PaperCompiler is written against `from openai import OpenAI` and only ever calls
`client.chat.completions.create(model=..., messages=[...])`. Putting this package
first on PYTHONPATH makes those calls run `claude -p` under your login instead,
without editing PaperCompiler. It implements exactly the surface PaperCompiler
reads (`choices[0].message.content`, `model_dump_json()` with a `usage` block) and
nothing else. The requested `model` is ignored; set PF_CLAUDE_MODEL to pick one.

Token counts in `usage` are estimates (characters / 4) so PaperCompiler's cost log
does not crash; the dollar figures it prints are meaningless here.
"""
import json
import os
import shutil
import subprocess
import time


class _Message:
    def __init__(self, content):
        self.role, self.content = "assistant", content


class _Choice:
    def __init__(self, content):
        self.index, self.finish_reason = 0, "stop"
        self.message = _Message(content)


class _Completion:
    def __init__(self, content, prompt_chars, model):
        self.model = model
        self.choices = [_Choice(content)]
        self._usage = {"prompt_tokens": prompt_chars // 4, "completion_tokens": len(content) // 4,
                       "total_tokens": (prompt_chars + len(content)) // 4,
                       "prompt_tokens_details": {"cached_tokens": 0}}

    def model_dump_json(self, **_):
        return json.dumps({"model": self.model, "usage": self._usage, "choices": [
            {"index": 0, "finish_reason": "stop",
             "message": {"role": "assistant", "content": self.choices[0].message.content}}]})


def _flatten(messages):
    parts = []
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(str(p.get("text", p)) if isinstance(p, dict) else str(p)
                                for p in content)
        parts.append(f"[{str(message.get('role', 'user')).upper()}]\n{content}")
    return "\n\n".join(parts)


class _Completions:
    def create(self, model=None, messages=None, **_ignored):
        executable = shutil.which("claude")
        if not executable:
            raise RuntimeError("claude CLI not found on PATH")
        prompt = _flatten(messages or [])
        command = [executable, "-p", "--output-format", "text", "--no-session-persistence",
                   "--permission-mode", "plan",
                   "--disallowedTools", "Bash", "Edit", "Write", "WebFetch", "WebSearch"]
        if os.environ.get("PF_CLAUDE_MODEL"):
            command += ["--model", os.environ["PF_CLAUDE_MODEL"]]
        timeout = float(os.environ.get("PF_CLAUDE_TIMEOUT", "1800"))
        last = ""
        for attempt in range(3):
            done = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", shell=False,
                                  timeout=timeout)
            if done.returncode == 0 and done.stdout.strip():
                return _Completion(done.stdout, len(prompt), model or "claude")
            last = (done.stderr or done.stdout or "empty response")[:300]
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"claude -p failed after 3 attempts: {last}")


class _Chat:
    completions = _Completions()


class OpenAI:
    def __init__(self, *args, **kwargs):
        self.chat = _Chat()
