"""Draft step, code step, Claude Code session, shim and sandbox: no model, no Docker."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory import results, sandbox  # noqa: E402
from factory.agents import session as session_mod  # noqa: E402
from factory.steps import code, write  # noqa: E402

SPEC = {"slots": [{"id": "main_acc", "kind": "value", "describe": "accuracy of ours"},
                  {"id": "loss_curve", "kind": "series", "describe": "training loss",
                   "x_label": "epoch", "y_label": "loss"}]}
DRAFT = ("\\documentclass{article}\\begin{document}Ours: \\PFVAL{main_acc}"
         "\\begin{figure}\\PFFIG{loss_curve}\\end{figure}\\end{document}\n")
GOOD = {"values": {"main_acc": 0.91},
        "series": {"loss_curve": {"x": [1, 2], "series": {"ours": [1.0, 0.5]}}}, "notes": "pilot"}


class Temp(unittest.TestCase):
    def setUp(self):
        self.project = pathlib.Path(tempfile.mkdtemp(prefix="pf-steps-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        (self.project / "_inputs").mkdir()


# -- Claude Code session -----------------------------------------------------

def make_stub(directory, body):
    script = directory / "stub.py"
    script.write_text(body, encoding="utf-8")
    launch = '"' + sys.executable + '" "' + str(script) + '"'
    (directory / "claude.cmd").write_text("@echo off\r\n" + launch + " %*\r\n", encoding="utf-8")
    (directory / "claude").write_text("#!/bin/sh\nexec " + launch + ' "$@"\n', encoding="utf-8")
    os.chmod(directory / "claude", 0o755)


class SessionTests(Temp):
    def test_session_runs_in_cwd_with_the_tool_allow_list_and_prompt_on_stdin(self):
        stub = self.project / "stub"
        stub.mkdir()
        make_stub(stub, "\n".join([
            "import json, os, sys",
            "text = sys.stdin.read()",
            "open(os.path.join(os.environ['STUB_OUT'], 'call.json'), 'w').write(json.dumps(",
            "    {'argv': sys.argv[1:], 'stdin': len(text), 'cwd': os.getcwd()}))",
            "open('made.txt', 'w').write('hi')",
            "if os.environ.get('STUB_FAIL'):",
            "    sys.stderr.write('boom'); sys.exit(3)",
            "print('done')"]) + "\n")
        work = self.project / "work"
        work.mkdir()
        env = {"PATH": str(stub) + os.pathsep + os.environ["PATH"], "STUB_OUT": str(self.project)}
        with mock.patch.dict(os.environ, env):
            done = session_mod.run_session("p" * 150000, work, ["Read", "Write", "Bash(python:*)"],
                                           add_dirs=[self.project], model="m1")
            self.assertEqual(done["stdout"].strip(), "done")
            call = json.loads((self.project / "call.json").read_text())
            self.assertEqual(call["stdin"], 150000)
            self.assertEqual(pathlib.Path(call["cwd"]).resolve(), work.resolve())
            argv = call["argv"]
            self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")
            allowed = argv[argv.index("--allowedTools") + 1:argv.index("--allowedTools") + 4]
            self.assertEqual(allowed, ["Read", "Write", "Bash(python:*)"])
            self.assertIn("--add-dir", argv)
            self.assertEqual(argv[argv.index("--model") + 1], "m1")
            self.assertTrue((work / "made.txt").is_file())
            with mock.patch.dict(os.environ, {"STUB_FAIL": "1"}):
                with self.assertRaisesRegex(ValueError, "exited 3"):
                    session_mod.run_session("x", work, ["Read"])


# -- S2 draft ----------------------------------------------------------------

class FakeAgent:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def run(self, prompt, validator, schema_path=None, repair_hint=""):
        self.prompts.append(prompt)
        problems = validator(self.payload)
        if problems:
            raise write.LoopExhausted("; ".join(problems), [])
        return {"payload": self.payload, "turns": 1}


class DraftStepTests(Temp):
    def setUp(self):
        super().setUp()
        (self.project / "1_idea").mkdir()
        (self.project / "1_idea" / "idea.md").write_text("# Idea\nTest whether X beats Y.\n",
                                                          encoding="utf-8")
        self.skills = self.project / "skills"
        (self.skills / "paper-orchestra").mkdir(parents=True)
        (self.skills / "paper-orchestra" / "SKILL.md").write_text("skill", encoding="utf-8")
        self.prompts = []

    def make_session(self, drafts):
        """Each call writes the next draft to workspace/final/paper.tex (or just records)."""
        queue = list(drafts)

        def session(prompt, **kw):
            self.prompts.append(prompt)
            if queue:
                target = pathlib.Path(kw["cwd"]) / "workspace" / "final" / "paper.tex"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(queue.pop(0), encoding="utf-8")
            self.options = kw
            return {"stdout": "", "returncode": 0}
        return session

    def build_pdf(self, build, name):
        pdf = pathlib.Path(build) / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.5 fake")
        return pdf

    def go(self, drafts, **kwargs):
        kwargs.setdefault("build_pdf", self.build_pdf)
        return write.run(self.project, {}, agent_factory=lambda: FakeAgent(SPEC),
                         session=self.make_session(drafts), skills_dir=self.skills, **kwargs)

    def test_draft_has_empty_slots_a_saved_spec_and_the_macros(self):
        receipt = self.go([DRAFT])
        paper = self.project / "2_paper"
        tex = (paper / "paper.tex").read_text(encoding="utf-8")
        self.assertIn("\\PFVAL{main_acc}", tex)
        self.assertEqual(tex.count(results.MARKER), 1)
        self.assertEqual(json.loads((paper / "results_spec.json").read_text()), SPEC)
        self.assertTrue((paper / "paper.pdf").is_file())
        self.assertTrue((paper / "build" / "paper.tex").is_file())
        self.assertEqual(receipt["slots"], 2)
        plan = (paper / "workspace" / "inputs" / "experimental_log.md").read_text(encoding="utf-8")
        self.assertIn("NO EXPERIMENT HAS BEEN RUN", plan)
        self.assertIn("\\PFFIG{loss_curve}", plan)
        self.assertEqual(len(self.prompts), 1)

    def test_the_number_check_ignores_our_own_macro_constants_but_flags_real_decimals(self):
        self.assertEqual(self.go([DRAFT])["numbers_to_check"], [])
        shutil.rmtree(self.project / "2_paper")
        flagged = self.go([DRAFT.replace("Ours:", "Ours beat it by 3.7 points. Ours:")])
        self.assertEqual(flagged["numbers_to_check"], ["3.7"])

    def test_empty_slots_render_as_tbd_not_as_a_glyph_a_reader_cannot_extract(self):
        self.assertIn("TBD", results.MACROS)
        self.assertNotIn("--}", results.MACROS)

    def test_session_gets_the_skills_dir_and_the_results_contract(self):
        self.go([DRAFT])
        self.assertIn("RESULTS CONTRACT", self.prompts[0])
        self.assertIn("paper-orchestra", self.prompts[0])
        self.assertEqual(self.options["add_dirs"], [self.skills])
        self.assertIn("WebSearch", self.options["tools"])

    def test_a_draft_that_forgets_a_slot_is_sent_back_for_repair(self):
        self.go([DRAFT.replace("\\PFVAL{main_acc}", "0.5"), DRAFT])
        self.assertEqual(len(self.prompts), 2)
        self.assertIn("PROBLEMS", self.prompts[1])
        self.assertIn("main_acc", self.prompts[1])

    def test_a_draft_that_never_gets_fixed_blocks_instead_of_publishing(self):
        bad = DRAFT.replace("\\PFVAL{main_acc}", "0.5")
        with self.assertRaisesRegex(ValueError, "still has problems"):
            self.go([bad, bad, bad])
        self.assertFalse((self.project / "2_paper" / "paper.tex").exists())

    def test_a_draft_that_does_not_compile_is_repaired(self):
        calls = []

        def flaky(build, name):
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("LaTeX build failed: Undefined control sequence")
            return self.build_pdf(build, name)

        self.go([DRAFT, DRAFT], build_pdf=flaky)
        self.assertEqual(len(calls), 2)
        self.assertIn("Undefined control sequence", self.prompts[1])

    def test_missing_skills_or_idea_are_clear_errors(self):
        with self.assertRaisesRegex(ValueError, "skills not found"):
            write.run(self.project, {}, skills_dir=self.project / "nope")
        (self.project / "1_idea" / "idea.md").unlink()
        with self.assertRaisesRegex(ValueError, "idea step first"):
            self.go([DRAFT])


# -- S4 code -----------------------------------------------------------------

class FakeSandbox:
    """Writes results.json the way a successful harness would, or not at all."""

    image = sandbox.DEFAULT_IMAGE

    def __init__(self, outcomes):
        self.outcomes, self.installed, self.runs = list(outcomes), 0, 0

    def install(self, repo, deps, timeout=0):
        self.installed += 1
        return {"status": "PASS", "stdout": "", "stderr": ""}

    def run(self, repo, command, out_dir, deps=None, data=None, timeout=0):
        self.runs += 1
        outcome = self.outcomes.pop(0)
        if outcome is not None:
            pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
            (pathlib.Path(out_dir) / "results.json").write_text(json.dumps(outcome))
        return {"status": "PASS" if outcome else "FAIL", "returncode": 0 if outcome else 1,
                "stdout": "", "stderr": "Traceback: boom" if outcome is None else ""}


HARNESS = ("import os, json\nfrom model import train\n"
           "out = os.environ['PF_OUT_DIR'] + '/results.json'\n# main_acc loss_curve\n")


class CodeStepTests(Temp):
    def setUp(self):
        super().setUp()
        (self.project / "2_paper").mkdir()
        (self.project / "2_paper" / "paper.tex").write_text(DRAFT, encoding="utf-8")
        (self.project / "2_paper" / "results_spec.json").write_text(json.dumps(SPEC))
        self.prompts, self.options = [], None

    def session(self, harness=HARNESS, choices=("optimizer not stated",)):
        def run(prompt, **kw):
            self.prompts.append(prompt)
            self.options = kw
            repo = self.project / "4_code" / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            if len(self.prompts) == 1:
                (repo / "model.py").write_text("def train(): pass\n", encoding="utf-8")
                (repo / "pf_run.py").write_text(harness, encoding="utf-8")
                artifacts = self.project / "4_code" / "artifacts"
                artifacts.mkdir(exist_ok=True)
                (artifacts / "open_design_choices.json").write_text(json.dumps(list(choices)))
            return {"stdout": "", "returncode": 0}
        return run

    def go(self, outcomes, context=None, **kwargs):
        box = FakeSandbox(outcomes)
        result = code.run(self.project, context or {}, sandbox=box,
                          session=kwargs.pop("session", None) or self.session(), **kwargs)
        return result, box

    def test_good_run_fills_every_slot_and_logs_pilot_results(self):
        result, box = self.go([GOOD])
        out = self.project / "4_code"
        saved = json.loads((out / "results.json").read_text())
        self.assertEqual(saved["values"]["main_acc"], 0.91)
        self.assertEqual(saved["scale"], "pilot")
        self.assertEqual(saved["mode"], "agent")
        log = (out / "experimental_log.generated.md").read_text()
        self.assertIn("| main_acc | 0.91 |", log)
        self.assertIn("pilot scale", log)
        self.assertEqual(len(json.loads((out / "unresolved.json").read_text())), 1)
        self.assertEqual(box.runs, 1)
        self.assertEqual(code.artifact_ok(self.project)[0], True)

    def test_the_session_reads_papercompiler_and_the_empty_slots_and_has_no_shell(self):
        self.go([GOOD])
        prompt = self.prompts[0]
        self.assertIn("PaperCompiler", prompt)
        self.assertIn("main_acc (value): accuracy of ours", prompt)
        self.assertIn("EMPTY", prompt)
        self.assertIn("PF_OUT_DIR", prompt)
        self.assertNotIn("Bash", self.options["tools"])
        self.assertEqual(self.options["add_dirs"], [code.PAPERCOMPILER])

    def test_failed_run_goes_back_to_claude_with_the_error_then_succeeds(self):
        result, box = self.go([None, GOOD])
        self.assertEqual(box.runs, 2)
        self.assertEqual(len(self.prompts), 2)
        self.assertIn("Traceback: boom", self.prompts[1])
        self.assertEqual([a["run"] for a in result["attempts"]], ["FAIL", "PASS"])

    def test_a_slot_the_code_never_filled_is_repaired_not_ignored(self):
        partial = {"values": {"main_acc": 0.91}}
        result, box = self.go([partial, GOOD])
        self.assertIn("loss_curve", self.prompts[1])
        self.assertEqual(box.runs, 2)

    def test_harness_that_ignores_a_slot_is_fixed_before_spending_a_sandbox_run(self):
        inner = self.session(harness=HARNESS.replace("loss_curve", ""))

        def fixer(prompt, **kw):
            inner(prompt, **kw)
            if len(self.prompts) == 2:  # the repair session fixes the harness
                (self.project / "4_code" / "repo" / "pf_run.py").write_text(HARNESS, encoding="utf-8")
            return {"stdout": "", "returncode": 0}

        result, box = self.go([GOOD], session=fixer)
        self.assertEqual(box.runs, 1)  # only the run after the repair
        self.assertIn("never mentioned", self.prompts[1])

    def test_no_valid_results_after_all_attempts_blocks_without_inventing_anything(self):
        with self.assertRaisesRegex(ValueError, "did not produce results for every slot"):
            self.go([None, None, None])
        self.assertFalse((self.project / "4_code" / "results.json").exists())

    def test_docker_down_blocks_before_any_model_call(self):
        with self.assertRaisesRegex(ValueError, "daemon is not running"):
            code.run(self.project, {}, session=lambda *a, **k: self.fail("model was called"),
                     health=lambda: {"status": "BLOCK", "remedy": "start Docker Desktop",
                                     "detail": "docker is installed but its daemon is not running"})

    def test_a_session_that_edits_papercompiler_is_refused(self):
        fake_vendor = self.project / "vendor"
        fake_vendor.mkdir()
        (fake_vendor / "README.md").write_text("original", encoding="utf-8")
        inner = self.session()

        def tamper(prompt, **kw):
            (fake_vendor / "README.md").write_text("changed", encoding="utf-8")
            return inner(prompt, **kw)

        with mock.patch.object(code, "PAPERCOMPILER", fake_vendor):
            with self.assertRaisesRegex(ValueError, "modified vendor/PaperCompiler"):
                self.go([GOOD], session=tamper)

    def test_pipeline_mode_runs_papercompiler_scripts_then_a_harness_session(self):
        called = []

        def build_repo(project, context):
            called.append(1)
            repo = pathlib.Path(project) / "4_code" / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / "model.py").write_text("x = 1\n", encoding="utf-8")
            return repo

        result, box = self.go([GOOD], {"code_mode": "pipeline"}, build_repo=build_repo)
        self.assertEqual(called, [1])
        self.assertIn("Add the results harness", self.prompts[0])
        self.assertEqual(result["mode"], "pipeline")

    def test_unknown_mode_is_refused(self):
        with self.assertRaisesRegex(ValueError, "code_mode"):
            self.go([GOOD], {"code_mode": "magic"})

    def test_open_design_choices_become_weaknesses_for_the_writer(self):
        path = self.project / "o.json"
        path.write_text(json.dumps(["optimizer not stated", "seed unspecified"]))
        items = code.unresolved_items(path)
        self.assertEqual(len(items), 2)
        self.assertIn("optimizer", items[0]["issue"])
        path.write_text(json.dumps({"a": {"open_design_choices": [{"what": "lr"}]}}))
        self.assertIn("lr", code.unresolved_items(path)[0]["issue"])
        self.assertEqual(code.unresolved_items(self.project / "missing.json"), [])

    def test_pipeline_stage_list_is_papercompilers_own_on_latex_input(self):
        stage_list, _ = code.pipeline_commands(self.project / "paper.tex", self.project / "a",
                                               self.project / "repo")
        self.assertEqual([s[0] for s in stage_list], [
            "1_translating", "1_5_reference", "2_reconciling", "3_architecting", "3_5_info",
            "4_contracting", "5_engineering"])
        self.assertIn("LaTeX", stage_list[0][1])
        for _, args, _ in stage_list:
            self.assertTrue((code.PAPERCOMPILER / "codes" / args[0]).is_file(), args[0])


# -- shim, sandbox, stdin ----------------------------------------------------

class OpenAIShimTests(Temp):
    """PaperCompiler's `from openai import OpenAI` is answered by the claude CLI."""

    def test_chat_completion_goes_through_claude_stdin_and_has_the_shape_it_reads(self):
        stub = self.project / "stub"
        stub.mkdir()
        make_stub(stub, "import sys\nprint('ANSWER:' + str(len(sys.stdin.read())))\n")
        program = "\n".join([
            "import json",
            "from openai import OpenAI",
            "client = OpenAI(api_key='x')",
            "r = client.chat.completions.create(model='o3-mini', reasoning_effort='high',",
            "    messages=[{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'U' * 100000}])",
            "d = json.loads(r.model_dump_json())",
            "print(r.choices[0].message.content.strip(), d['choices'][0]['message']['content'].strip(),",
            "      d['usage']['prompt_tokens'] > 0, d['usage']['prompt_tokens_details']['cached_tokens'])",
        ])
        env = {**os.environ, "PATH": str(stub) + os.pathsep + os.environ["PATH"],
               "PYTHONPATH": str(ROOT / "factory" / "shims")}
        done = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True,
                              env=env, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        first, second, positive, cached = done.stdout.split()
        self.assertTrue(first.startswith("ANSWER:100"), done.stdout)
        self.assertEqual(first, second)
        self.assertEqual((positive, cached), ("True", "0"))


class SandboxTests(unittest.TestCase):
    def test_an_unpinned_image_is_refused(self):
        for bad in ("python:latest", "", None, "python@sha256:abc"):
            with self.assertRaises(ValueError):
                sandbox.require_digest_pin(bad)
        self.assertEqual(sandbox.require_digest_pin(sandbox.DEFAULT_IMAGE), sandbox.DEFAULT_IMAGE)

    def test_install_has_network_but_the_run_has_none_and_a_read_only_repo(self):
        repo = pathlib.Path(tempfile.mkdtemp(prefix="pf-sb-"))
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        (repo / "requirements.txt").write_text("numpy\n", encoding="utf-8")
        (repo / "data").mkdir()
        seen = []

        def fake_run(command, **kwargs):
            seen.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        box = sandbox.Sandbox(allow_network_install=True)
        with mock.patch("factory.sandbox.shutil.which", return_value="docker"), \
                mock.patch("factory.sandbox.subprocess.run", fake_run):
            box.install(repo, repo / "deps")
            box.run(repo, ["python", "pf_run.py"], repo / "out", deps=repo / "deps",
                    data=repo / "data")
        install, run = seen
        self.assertEqual(install[install.index("--network") + 1], "bridge")
        self.assertEqual(run[run.index("--network") + 1], "none")
        self.assertIn("--read-only", run)
        self.assertIn("--cap-drop", run)
        self.assertTrue(any(part.endswith(":/workspace:ro") for part in run))
        self.assertTrue(any(part.endswith(":/out:rw") for part in run))
        self.assertTrue(any(part.endswith(":/data:ro") for part in run))
        self.assertIn(sandbox.DEFAULT_IMAGE, run)


class AgentStdinTests(Temp):
    """A whole manuscript must reach the CLI on stdin, not on the command line."""

    def test_long_prompt_reaches_claude_on_stdin_and_json_comes_back(self):
        from factory.agents.loop import AgentLoop
        stub = self.project / "stub"
        stub.mkdir()
        make_stub(stub, "\n".join([
            "import json, sys",
            "text = sys.stdin.read()",
            "print(json.dumps({'structured_output': {'chars': len(text)}}))"]) + "\n")
        with mock.patch.dict(os.environ, {"PATH": str(stub) + os.pathsep + os.environ["PATH"]}):
            result = AgentLoop("claude").run("x" * 200000, lambda payload: [])
        self.assertEqual(result["payload"]["chars"], 200000)


if __name__ == "__main__":
    unittest.main()
