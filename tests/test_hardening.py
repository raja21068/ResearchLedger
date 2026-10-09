"""Regression tests for unsafe filesystem access, stale checkpoints and false passes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from factory import results, sandbox
from factory.cli.main import project_slug
from factory.config import validate_context
from factory.io import atomic_json
from factory.pipeline import Orchestrator, stages
from factory.pipeline.lock import exclusive_run
from factory.pipeline.provenance import input_signature
from factory.steps import code


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="pf-hardening-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        (self.project / "_inputs").mkdir()

    def test_project_slug_accepts_human_names(self):
        self.assertEqual(project_slug("  My First Project "), "my-first-project")

    def test_project_slug_rejects_directory_traversal_and_absolute_paths(self):
        for name in ("../private", "../../tmp", "a/b", r"C:\\Windows", "..", ".",
                     "a\\b", "", "*", "-bad", "a" * 80):
            with self.subTest(name=name), self.assertRaises(ValueError):
                project_slug(name)

    def test_context_rejects_malformed_and_unbounded_options(self):
        invalid = (["not a dict"], {"code_run_attempts": -1}, {"review_max_rounds": 100},
                   {"allow_network_install": "yes"}, {"review_thresholds": {"impact": 99}},
                   {"review_thresholds": {"impact": float("nan")}},
                   {"review_thresholds": {"anything": 8}}, {"code_mode": "unknown"})
        for context in invalid:
            with self.subTest(context=context), self.assertRaises(ValueError):
                validate_context(context)
        self.assertEqual(validate_context({"allow_network_install": True}),
                         {"allow_network_install": True})

    def test_input_hash_changes_on_topic_and_data_change(self):
        topic = self.project / "_inputs" / "topic.md"
        topic.write_text("original")
        before = input_signature(self.project, "S1", {})
        topic.write_text("revised")
        self.assertNotEqual(before, input_signature(self.project, "S1", {}))
        data = self.project / "_inputs" / "data"
        data.mkdir()
        (data / "data.csv").write_text("1,2,3")
        second = input_signature(self.project, "S4", {})
        (data / "data.csv").write_text("1,2,4")
        self.assertNotEqual(second, input_signature(self.project, "S4", {}))

    def test_signature_rejects_symlink_in_inputs(self):
        foreign = self.project / "foreign.txt"
        foreign.write_text("secret")
        (self.project / "_inputs" / "linked.txt").symlink_to(foreign)
        with self.assertRaisesRegex(ValueError, "symlink"):
            input_signature(self.project, "S1", {})

    def test_run_lock_blocks_duplicate_controller_and_cleans_up(self):
        with exclusive_run(self.project):
            with self.assertRaisesRegex(ValueError, "another run"):
                with exclusive_run(self.project):
                    pass
        self.assertFalse((self.project / "control" / "run.lock").exists())

    def test_atomic_json_preserves_previous_data_if_replace_fails(self):
        file = self.project / "checkpoint.json"
        file.write_text('{"safe": true}')
        with mock.patch("factory.io.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                atomic_json(file, {"safe": False})
        self.assertEqual(json.loads(file.read_text()), {"safe": True})
        self.assertEqual(list(self.project.glob(".*.tmp")), [])

    def test_result_keys_reject_latex_injection(self):
        file = self.project / "results.json"
        file.write_text(json.dumps({"values": {"bad\\end{document}": 1}}))
        with self.assertRaisesRegex(ValueError, "invalid slot ids"):
            results.read_results(file)

    def test_result_series_reject_nonfinite_x(self):
        file = self.project / "results.json"
        file.write_text('{"series":{"curve":{"x":[NaN],"series":{"a":[1]}}}}')
        with self.assertRaisesRegex(ValueError, "x-axis"):
            results.read_results(file)

    def test_sandbox_offline_install_by_default(self):
        (self.project / "requirements.txt").write_text("numpy")
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")
        with mock.patch("factory.sandbox.shutil.which", return_value="docker"), \
             mock.patch("factory.sandbox.subprocess.run", side_effect=run):
            sandbox.Sandbox().install(self.project, self.project / "deps")
        self.assertEqual(calls[0][calls[0].index("--network") + 1], "none")
        self.assertIn("--no-index", calls[0])

    def test_generated_repo_symlink_rejected(self):
        repo = self.project / "repo"
        repo.mkdir()
        (repo / "pf_run.py").write_text("# PF_OUT_DIR results.json metric\n")
        (repo / "escape.py").symlink_to(self.project / "foreign.py")
        self.assertIn("symlinks", " ".join(code.repo_problems(repo, [
            {"id": "metric", "kind": "value"}])))

    def test_s5_cannot_pass_when_automated_thresholds_missed(self):
        report = self.project / "5_refine" / "report.json"
        report.parent.mkdir()
        report.write_text(json.dumps({"schema_version": 1, "status": "MAX_ROUNDS",
                                      "final_scores": {"quality": 6.5}, "rounds": [{}]}))
        passed, reason = stages.artifact_valid(self.project, "S5")
        self.assertFalse(passed)
        self.assertIn("did not reach", reason)


class ProvenanceResumeTests(unittest.TestCase):
    def setUp(self):
        from test_pipeline import SPEC, DRAFT, RESULTS, make_idea, review_report
        self.project = Path(tempfile.mkdtemp(prefix="pf-provenance-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        (self.project / "_inputs").mkdir()
        (self.project / "_inputs" / "ideas.json").write_text(json.dumps({"ideas": [
            make_idea("a"), make_idea("b", 8)]}))
        self.called = []
        artifacts = {"S2": {"2_paper/results_spec.json": SPEC, "2_paper/paper.tex": DRAFT},
                     "S3": {"3_review/report.json": review_report("SINGLE_PASS")},
                     "S4": {"4_code/results.json": RESULTS},
                     "S5": {"5_refine/report.json": review_report()}}
        for stage_id, values in artifacts.items():
            real = stages.BY_ID[stage_id]["driver"]
            def driver(project, source, context, _stage=stage_id, _files=values):
                self.called.append(_stage)
                for name, value in _files.items():
                    path = Path(project) / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value if isinstance(value, str) else json.dumps(value))
            stages.BY_ID[stage_id]["driver"] = driver
            self.addCleanup(stages.BY_ID[stage_id].__setitem__, "driver", real)

    def test_resume_skips_only_when_inputs_and_outputs_still_match(self):
        self.assertEqual(Orchestrator(self.project).run()["status"], "COMPLETE")
        self.assertEqual([r["status"] for r in Orchestrator(self.project).run(resume=True)["stages"]],
                         ["SKIPPED"] * 5)
        (self.project / "_inputs" / "context.json").write_text('{"idea_count": 2}')
        self.called.clear()
        again = Orchestrator(self.project).run(resume=True)
        self.assertEqual(again["status"], "COMPLETE")
        self.assertEqual(self.called, ["S2", "S3", "S4", "S5"])
        self.assertEqual(again["stages"][0]["status"], "PASS")

    def test_upstream_artifact_changed_forces_downstream_reexecution(self):
        Orchestrator(self.project).run()
        (self.project / "2_paper" / "paper.tex").write_text("changed")
        again = Orchestrator(self.project).run(resume=True)
        self.assertEqual(again["stages"][0]["status"], "SKIPPED")
        self.assertEqual(again["stages"][1]["status"], "PASS")
        self.assertTrue(all(r["status"] == "PASS" for r in again["stages"][2:]))

    def test_failing_upstream_stage_removes_stale_downstream_completion(self):
        Orchestrator(self.project).run()
        original = stages.BY_ID["S3"]["driver"]
        def fail(*args):
            raise ValueError("simulated reviewer outage")
        stages.BY_ID["S3"]["driver"] = fail
        self.addCleanup(stages.BY_ID["S3"].__setitem__, "driver", original)
        again = Orchestrator(self.project).run(start="S3", stop="S3")
        self.assertEqual(again["status"], "BLOCKED")
        self.assertEqual(again["state"], "PAPER_READY")
        self.assertEqual(again["historical_state"], "REFINED")
        self.assertEqual(list(Orchestrator(self.project).completed()), ["S1", "S2"])

    def test_tampered_generated_code_invalidates_code_and_refinement(self):
        Orchestrator(self.project).run()
        repo = self.project / "4_code" / "repo"
        repo.mkdir(parents=True)
        # Stage S4's supporting output signature originally recorded a missing repo.
        (repo / "model.py").write_text("print('different')")
        self.called.clear()
        again = Orchestrator(self.project).run(resume=True)
        self.assertEqual([r["status"] for r in again["stages"][:3]], ["SKIPPED"] * 3)
        self.assertEqual(self.called, ["S4", "S5"])

    def test_tampered_final_manuscript_invalidates_refinement(self):
        Orchestrator(self.project).run()
        final = self.project / "5_refine" / "final"
        final.mkdir(parents=True)
        (final / "paper.tex").write_text("post-review changes")
        self.called.clear()
        again = Orchestrator(self.project).run(resume=True)
        self.assertEqual([r["status"] for r in again["stages"][:4]], ["SKIPPED"] * 4)
        self.assertEqual(self.called, ["S5"])

    def test_explicit_start_needs_verified_prerequisites(self):
        with self.assertRaisesRegex(ValueError, "prerequisite S1"):
            Orchestrator(self.project).run(start="S3", stop="S3")


if __name__ == "__main__":
    unittest.main()

class QualityAuditTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="pf-audit-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        (self.project / "_inputs").mkdir()

    def test_audit_explains_why_a_high_score_is_not_publication_approval(self):
        from factory.quality import audit
        report = audit(self.project)
        self.assertFalse(report["publication_ready"])
        self.assertEqual(report["scientific_status"], "NOT_EVALUATED")
        path = self.project / "control" / "quality_report.md"
        self.assertTrue(path.exists())
        self.assertIn("NOT CERTIFIED", path.read_text())

    def test_falsifier_needs_a_finite_threshold(self):
        from factory.steps.idea import falsifier_problems
        idea = {"falsifier": {"statement": "The gain is below the expected threshold",
                              "metric": "gain", "threshold": float("inf")}}
        self.assertTrue(falsifier_problems(idea))

    def test_results_file_enforces_bounded_payload_size(self):
        path = self.project / "results.json"
        path.write_text('{"values":{"x":1}}')
        with mock.patch.object(results, "MAX_RESULTS_BYTES", 5):
            with self.assertRaisesRegex(ValueError, "safety limit"):
                results.read_results(path)

    def test_control_directory_symlink_rejected(self):
        foreign = self.project / "foreign"
        foreign.mkdir()
        (self.project / "control").symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "control directory"):
            with exclusive_run(self.project):
                pass
