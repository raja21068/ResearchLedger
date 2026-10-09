"""Idea, review loop, code step and orchestrator, with no model, no network, no Docker."""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.agents.loop import LoopExhausted  # noqa: E402
from factory.pipeline import Orchestrator, stages  # noqa: E402
from factory import results  # noqa: E402
from factory.steps import idea, review  # noqa: E402


def review_of(reviewer, score=7):
    return {"reviewer_id": reviewer, "novelty": score, "importance": score,
            "feasibility": score, "falsifiability": score, "evidence_fit": score}


def make_idea(idea_id, score=7, falsifier=True):
    value = {"id": idea_id, "title": f"Idea {idea_id}", "hypothesis": "X improves Y",
             "reviews": [review_of("r1", score), review_of("r2", score)]}
    if falsifier:
        value["falsifier"] = {"statement": "Accuracy gain over baseline is below one point",
                              "metric": "accuracy_gain", "threshold": 1.0}
    return value


class TempProject(unittest.TestCase):
    def setUp(self):
        self.project = pathlib.Path(tempfile.mkdtemp(prefix="pf-test-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        (self.project / "_inputs").mkdir()

    def put(self, name, payload):
        path = self.project / "_inputs" / name
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload),
                        encoding="utf-8")
        return path


# -- S1 ----------------------------------------------------------------------

class IdeaStepTests(TempProject):
    def test_highest_scoring_falsifiable_idea_wins_and_idea_md_is_written(self):
        source = self.put("ideas.json", {"ideas": [make_idea("a", 6), make_idea("b", 9)]})
        report = idea.select(self.project, source)
        self.assertEqual(report["winner"], "b")
        text = (self.project / "1_idea" / "idea.md").read_text(encoding="utf-8")
        self.assertIn("# Idea b", text)
        self.assertIn("accuracy_gain", text)

    def test_unfalsifiable_idea_is_rejected_however_well_it_scores(self):
        source = self.put("ideas.json", {"ideas": [make_idea("a", 5),
                                                   make_idea("b", 10, falsifier=False)]})
        report = idea.select(self.project, source)
        self.assertEqual(report["winner"], "a")
        self.assertEqual([r["id"] for r in report["rejected_unfalsifiable"]], ["b"])

    def test_free_text_falsifier_does_not_count(self):
        bad = make_idea("a")
        bad["falsifier"] = "it would fail if it does not work"
        source = self.put("ideas.json", {"ideas": [bad, make_idea("b", falsifier=False)]})
        with self.assertRaisesRegex(ValueError, "falsifiability gate"):
            idea.select(self.project, source)

    def test_needs_two_independent_reviews(self):
        thin = make_idea("a")
        thin["reviews"] = thin["reviews"][:1]
        source = self.put("ideas.json", {"ideas": [thin, make_idea("b")]})
        with self.assertRaisesRegex(ValueError, "two independent reviews"):
            idea.select(self.project, source)


class IdeaGenerationTests(TempProject):
    """Ideas generated from topic.md by (fake) Claude calls, then gated like supplied ones."""

    def agent_factory(self, ideas, reviews):
        class Agent:
            def __init__(self, payload):
                self.payload = payload

            def run(self, prompt, validator, schema_path=None, repair_hint=""):
                problems = validator(self.payload)
                if problems:
                    raise LoopExhausted("; ".join(problems), [])
                return {"payload": self.payload, "turns": 1}

        queue = [{"ideas": ideas}, {"reviews": reviews[0]}, {"reviews": reviews[1]}]
        return lambda: Agent(queue.pop(0))

    def scored(self, scores):
        return [{"idea_id": i, "novelty": n, "importance": n, "feasibility": n,
                 "falsifiability": n, "evidence_fit": n} for i, n in scores.items()]

    def raw(self, idea_id, falsifier=True):
        value = make_idea(idea_id, falsifier=falsifier)
        del value["reviews"]
        value["method"] = "run it"
        return value

    def test_topic_becomes_ideas_scored_by_two_reviewers_and_the_best_wins(self):
        self.put("topic.md", "robust federated learning")
        factory = self.agent_factory([self.raw("a"), self.raw("b")],
                                     [self.scored({"a": 5, "b": 9}), self.scored({"a": 6, "b": 8})])
        report = idea.run(self.project, {}, agent_factory=factory)
        self.assertEqual(report["winner"], "b")
        self.assertTrue(report["generated"])
        self.assertIn("separate Claude calls", report["caveat"])
        generated = json.loads((self.project / "1_idea" / "ideas.generated.json").read_text())
        self.assertEqual({r["reviewer_id"] for r in generated["ideas"][0]["reviews"]},
                         {"novelty-skeptic", "methods-realist"})
        self.assertTrue((self.project / "1_idea" / "idea.md").is_file())

    def test_a_generated_idea_without_a_measurable_falsifier_is_still_rejected(self):
        self.put("topic.md", "x")
        factory = self.agent_factory([self.raw("a"), self.raw("b", falsifier=False)],
                                     [self.scored({"a": 3, "b": 10}), self.scored({"a": 3, "b": 10})])
        report = idea.run(self.project, {}, agent_factory=factory)
        self.assertEqual(report["winner"], "a")

    def test_supplied_ideas_json_wins_over_generation(self):
        self.put("ideas.json", {"ideas": [make_idea("a", 6), make_idea("b", 9)]})
        self.put("topic.md", "ignored")
        self.assertEqual(idea.run(self.project, {}, agent_factory=lambda: 1 / 0)["winner"], "b")

    def test_neither_input_is_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, "ideas.json or topic.md"):
            idea.run(self.project, {})


# -- review ------------------------------------------------------------------

DIMENSIONS = review.dimensions()[0]
LONG_REVIEW = "A serious, anchored review. " * 30
ORIGINAL_TEX = ("\\documentclass{article}\\begin{document}"
                "Gain is 1.5 points \\cite{a}.\\end{document}\n")
METHODS = review.CATEGORIES["methods"]


def review_payload(mean=7, **overrides):
    """A valid reviewer response scoring every dimension `mean`, except overrides."""
    scores = [{"dimension": d, "score": overrides.get(d, mean), "justification": "because",
               "confidence": 0.8} for d in DIMENSIONS]
    return {"review_markdown": LONG_REVIEW, "scores": scores,
            "weaknesses": [{"location": "p1:L2", "issue": "claim too broad", "fix": "narrow it"}]}


def revision_payload(tex):
    return {"paper_tex": tex, "changes": ["narrowed the claim"]}


class FakeAgent:
    """Stands in for the Claude Code agent. Applies the real validators."""

    def __init__(self, reviews, revisions=()):
        self.reviews, self.revisions, self.calls = list(reviews), list(revisions), []

    def run(self, prompt, validator, schema_path=None, repair_hint=""):
        kind = "review" if schema_path == review.REVIEW_SCHEMA else "revise"
        self.calls.append(kind)
        payload = (self.reviews if kind == "review" else self.revisions).pop(0)
        problems = validator(payload)
        if problems:
            raise LoopExhausted("rejected: " + "; ".join(problems), [])
        return {"payload": payload, "turns": 1}


class ReviewHelpersTests(unittest.TestCase):
    def test_every_category_member_is_a_real_dimension(self):
        keys = {review._key(d) for d in DIMENSIONS}
        for category, members in review.CATEGORIES.items():
            for member in members:
                self.assertIn(review._key(member), keys, f"{category}: {member}")

    def test_prompt_light_has_role_task_dimensions_and_manuscript(self):
        text = review.review_prompt("[p1:L1] Hello manuscript")
        self.assertIn("evidence-locked", text)
        self.assertIn("Construct Clarity & Definition Audit", text)
        self.assertIn("Statistical rigor", text)
        self.assertNotIn("Journal/venue scope fit", text)
        self.assertNotIn("[PASTE MANUSCRIPT]", text)
        self.assertIn("[p1:L1] Hello manuscript", text)

    def test_prompt_full_agent_points_at_the_referee_package(self):
        text = review.review_prompt("[p1:L1] x", full_agent=True)
        self.assertIn("core/AGENT_SYSTEM.md", text)
        self.assertIn("never run commands or write files", text)

    def test_review_needs_every_dimension_and_twenty_scored(self):
        self.assertEqual(review.review_problems(review_payload(7), 20), [])
        partial = review_payload(7)
        partial["scores"] = partial["scores"][:10]
        self.assertTrue(any("missing for" in p for p in review.review_problems(partial, 20)))
        sparse = review_payload(7, **{d: None for d in DIMENSIONS[:35]})
        self.assertTrue(any("at least 20" in p for p in review.review_problems(sparse, 20)))

    def test_bad_scores_are_refused(self):
        self.assertTrue(review.review_problems(review_payload(7, **{DIMENSIONS[0]: 11}), 20))
        self.assertTrue(review.review_problems(review_payload(7, **{DIMENSIONS[0]: 7.5}), 20))

    def test_scores_fold_into_the_five_categories_ignoring_na(self):
        summary = review.score_summary(review_payload(
            8, **{"Importance of research problem": 4, "Scientific significance": None,
                  "Statistical rigor": 2}))
        categories = summary["categories"]
        self.assertEqual(categories["impact"], round((4 + 8) / 2, 2))  # NA excluded
        self.assertEqual(categories["novelty"], 8.0)
        self.assertEqual(categories["methods"], round((8 * (len(METHODS) - 1) + 2) / len(METHODS), 2))
        self.assertEqual(summary["not_applicable"], 1)
        self.assertEqual(summary["lowest"], {"dimension": "Statistical rigor", "score": 2})

    def test_thresholds_are_the_ones_you_set(self):
        self.assertEqual(review.THRESHOLDS, {"quality": 8.0, "impact": 9.0, "novelty": 8.3,
                                             "methods": 8.3, "readiness": 7.3})
        met, shortfall, detail = review.gap_to_thresholds(
            {"quality": 8.0, "impact": 9.0, "novelty": 8.3, "methods": 8.3, "readiness": 7.3},
            review.THRESHOLDS)
        self.assertTrue(met)
        self.assertEqual(shortfall, 0)
        met, shortfall, detail = review.gap_to_thresholds(
            {"quality": 8.0, "impact": 8.5, "novelty": None, "methods": 8.3, "readiness": 7.3},
            review.THRESHOLDS)
        self.assertFalse(met)
        self.assertEqual(shortfall, round(0.5 + 8.3, 3))  # an unassessable category counts in full
        self.assertFalse(detail["impact"]["met"])

    def test_revision_may_not_invent_numbers_or_citations(self):
        log = "accuracy 0.82"

        def problems(tex):
            return review.revision_problems(revision_payload(tex), ORIGINAL_TEX, log)

        self.assertEqual(problems(ORIGINAL_TEX), [])
        self.assertEqual(problems(ORIGINAL_TEX.replace("1.5", "0.82")), [])
        self.assertTrue(any("9.99" in p for p in problems(ORIGINAL_TEX.replace("1.5", "9.99"))))
        self.assertTrue(any("citation" in p for p in
                            problems(ORIGINAL_TEX.replace("\\cite{a}", "\\cite{a,b}"))))
        self.assertTrue(problems("just text"))

    def test_margin_line_numbers_are_dropped_but_a_lone_value_on_an_unnumbered_page_is_kept(self):
        numbered = [f"{i:03d}" for i in range(20)] + ["real text line", "Table 1", "0.91"]
        self.assertEqual(review.strip_margin_numbers(numbered), ["real text line", "Table 1", "0.91"])
        unnumbered = ["Table 1", "100", "0.91"]
        self.assertEqual(review.strip_margin_numbers(unnumbered), unnumbered)

    @unittest.skipUnless(shutil.which("pdflatex"), "pdflatex not installed")
    def test_real_pdf_round_trip_gives_page_and_line_markers(self):
        work = pathlib.Path(tempfile.mkdtemp(prefix="pf-pdf-"))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        sentences = "\n\n".join(f"Sentence number {i} about calibration." for i in range(8))
        (work / "paper.tex").write_text(
            "\\documentclass{article}\\begin{document}\n" + sentences + "\n\\end{document}\n",
            encoding="utf-8")
        text = review.pdf_text(review.compile_pdf(work, "paper.tex"))
        self.assertTrue(text.startswith("[p1:L1]"))
        self.assertIn("calibration", text)


class ReviewLoopTests(TempProject):
    def setUp(self):
        super().setUp()
        paper = self.project / "2_paper"
        (paper / "build").mkdir(parents=True)
        (paper / "paper.tex").write_text(ORIGINAL_TEX, encoding="utf-8")
        (paper / "build" / "paper.tex").write_text(ORIGINAL_TEX, encoding="utf-8")
        (paper / "paper.pdf").write_bytes(b"%PDF-original")
        self.put("experimental_log.md", "accuracy 0.82\n")

    def build(self, workdir, name):
        pdf = pathlib.Path(workdir) / "paper.pdf"
        pdf.write_bytes(b"%PDF-revised")
        return pdf

    def go(self, agent, **kwargs):
        context = kwargs.pop("context", {})
        return review.run(self.project, context, agent_factory=lambda s, w: agent,
                          pdf_to_text=lambda pdf: "[p1:L1] text", build=self.build, **kwargs)

    def final_tex(self, folder="3_review"):
        return (self.project / folder / "final" / "paper.tex").read_text(encoding="utf-8")

    def test_all_five_thresholds_met_in_round_one_makes_no_revision(self):
        agent = FakeAgent([review_payload(9)])
        report = self.go(agent)
        self.assertEqual(report["status"], "TARGET_REACHED")
        self.assertEqual(agent.calls, ["review"])
        self.assertTrue(all(row["met"] for row in report["final_thresholds"].values()))
        self.assertTrue((self.project / "3_review" / "final" / "paper.pdf").is_file())

    def test_one_category_below_threshold_keeps_the_loop_going(self):
        low_methods = {name: 7 for name in METHODS}
        agent = FakeAgent([review_payload(9, **low_methods)])
        report = self.go(agent, context={"review_max_rounds": 1})
        self.assertEqual(report["status"], "MAX_ROUNDS")
        self.assertFalse(report["final_thresholds"]["methods"]["met"])
        self.assertTrue(report["final_thresholds"]["quality"]["met"])

    def test_thresholds_can_be_overridden_per_project(self):
        agent = FakeAgent([review_payload(7)])
        report = self.go(agent, context={"review_thresholds": {
            "quality": 6, "impact": 6, "novelty": 6, "methods": 6, "readiness": 6}})
        self.assertEqual(report["status"], "TARGET_REACHED")

    def test_single_pass_scores_but_never_revises(self):
        agent = FakeAgent([review_payload(6)])
        report = self.go(agent, revise=False)
        self.assertEqual(report["status"], "SINGLE_PASS")
        self.assertEqual(agent.calls, ["review"])

    def test_improving_revision_is_kept_and_reaches_target(self):
        revised = ORIGINAL_TEX.replace("Gain is", "Gain was")
        agent = FakeAgent([review_payload(6), review_payload(9)], [revision_payload(revised)])
        report = self.go(agent)
        self.assertEqual(report["status"], "TARGET_REACHED")
        self.assertEqual([r["categories"]["quality"] for r in report["rounds"]], [6.0, 9.0])
        self.assertEqual(report["final_round"], 2)
        self.assertEqual(self.final_tex(), revised)
        self.assertEqual(agent.calls, ["review", "revise", "review"])

    def test_revision_that_does_not_reduce_the_shortfall_is_discarded(self):
        revised = ORIGINAL_TEX.replace("Gain is", "Gain was")
        agent = FakeAgent([review_payload(6), review_payload(5)], [revision_payload(revised)])
        report = self.go(agent)
        self.assertEqual(report["status"], "NO_IMPROVEMENT")
        self.assertEqual(report["final_round"], 1)
        self.assertEqual(self.final_tex(), ORIGINAL_TEX)

    def test_seed_weaknesses_drive_a_revision_before_the_first_review(self):
        revised = ORIGINAL_TEX.replace("Gain is", "Gain was")
        agent = FakeAgent([review_payload(9)], [revision_payload(revised)])
        seed = [{"location": "PaperCompiler: open_design_choices", "issue": "optimizer unstated",
                 "fix": "state it"}]
        report = self.go(agent, seed_weaknesses=seed, out_name="5_refine",
                         log_text="accuracy 0.82\n| acc | 0.91 |")
        self.assertEqual(agent.calls, ["revise", "review"])
        self.assertIn("seed revision applied", report["seed"])
        self.assertEqual(self.final_tex("5_refine"), revised)
        self.assertEqual(report["final_paper"], "5_refine/final/paper.pdf")
        # the written paper is untouched
        self.assertEqual((self.project / "2_paper" / "paper.tex").read_text(), ORIGINAL_TEX)

    def test_results_from_the_log_may_enter_the_paper_but_nothing_else(self):
        agent = FakeAgent([review_payload(9)],
                          [revision_payload(ORIGINAL_TEX.replace("1.5", "0.91"))])
        report = self.go(agent, seed_weaknesses=[{"location": "p1", "issue": "x", "fix": "y"}],
                         log_text="| acc | 0.91 |")
        self.assertIn("applied", report["seed"])
        agent = FakeAgent([review_payload(9)],
                          [revision_payload(ORIGINAL_TEX.replace("1.5", "0.93"))])
        report = self.go(agent, seed_weaknesses=[{"location": "p1", "issue": "x", "fix": "y"}],
                         log_text="| acc | 0.91 |")
        self.assertIn("skipped", report["seed"])

    def test_revision_with_invented_numbers_is_rejected_and_loop_stops(self):
        agent = FakeAgent([review_payload(6)],
                          [revision_payload(ORIGINAL_TEX.replace("1.5", "9.99"))])
        report = self.go(agent)
        self.assertEqual(report["status"], "REVISION_REJECTED")
        self.assertEqual(report["final_round"], 1)

    def test_unusable_review_raises_instead_of_inventing_a_score(self):
        agent = FakeAgent([{"review_markdown": "short", "scores": [], "weaknesses": []}])
        with self.assertRaisesRegex(ValueError, "no usable review"):
            self.go(agent)

    def test_report_states_the_self_grading_caveat(self):
        report = self.go(FakeAgent([review_payload(9)]))
        self.assertIn("same model family", report["caveat"])




class GuardTests(ReviewLoopTests):
    def test_results_may_enter_only_through_macros_not_be_retyped(self):
        agent = FakeAgent([review_payload(9)], [revision_payload(ORIGINAL_TEX.replace("1.5", "0.91"))])
        report = self.go(agent, seed_weaknesses=[{"location": "p1", "issue": "x", "fix": "y"}],
                         log_text="| acc | 0.91 |", guard_text="author notes only")
        self.assertIn("skipped", report["seed"])  # 0.91 is shown to the reviser but not quotable

    def test_a_filled_source_dir_replaces_2_paper(self):
        source = self.project / "5_refine" / "source"
        (source / "build").mkdir(parents=True)
        (source / "paper.tex").write_text(ORIGINAL_TEX.replace("1.5", "2.5"), encoding="utf-8")
        (source / "paper.pdf").write_bytes(b"%PDF-filled")
        report = self.go(FakeAgent([review_payload(9)]), out_name="5_refine", source_dir=source)
        self.assertEqual(report["status"], "TARGET_REACHED")
        self.assertIn("2.5", self.final_tex("5_refine"))


# -- orchestrator ------------------------------------------------------------

def review_report(status="TARGET_REACHED"):
    return {"schema_version": 1, "status": status, "rounds": [{}],
            "final_scores": {"quality": 8.5, "impact": 9.1, "novelty": 8.4, "methods": 8.4,
                             "readiness": 7.5}}


SPEC = {"slots": [{"id": "acc", "kind": "value", "describe": "accuracy"},
                  {"id": "curve", "kind": "series", "describe": "loss curve"}]}
DRAFT = ORIGINAL_TEX.replace("Gain is 1.5 points", "Gain is \\PFVAL{acc}\\PFFIG{curve}")
RESULTS = {"schema_version": 1, "values": {"acc": 0.9},
           "series": {"curve": {"x": [1, 2], "series": {"a": [0.5, 0.4]}}}}


class OrchestratorTests(TempProject):
    """Draft, review, code and refine are stubbed; they need a model login and Docker."""

    def setUp(self):
        super().setUp()
        self.order = []

        def writer(files):
            def driver(project, source, context):
                for rel, content in files.items():
                    self.order.append(rel)
                    target = pathlib.Path(project) / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content if isinstance(content, str) else json.dumps(content),
                                      encoding="utf-8")
            return driver

        fakes = {"S2": writer({"2_paper/results_spec.json": SPEC, "2_paper/paper.tex": DRAFT}),
                 "S3": writer({"3_review/report.json": review_report("SINGLE_PASS")}),
                 "S4": writer({"4_code/results.json": RESULTS}),
                 "S5": writer({"5_refine/report.json": review_report()})}
        for stage, driver in fakes.items():
            real = stages.BY_ID[stage]["driver"]
            stages.BY_ID[stage]["driver"] = driver
            self.addCleanup(stages.BY_ID[stage].__setitem__, "driver", real)
        self.put("ideas.json", {"ideas": [make_idea("a"), make_idea("b", 8)]})

    def test_five_stages_run_in_order_and_state_reaches_refined(self):
        summary = Orchestrator(self.project, {}).run()
        self.assertEqual(summary["status"], "COMPLETE", summary["blocked"])
        self.assertEqual([s["stage"] for s in summary["stages"]], ["S1", "S2", "S3", "S4", "S5"])
        self.assertEqual(summary["state"], "REFINED")
        self.assertIn("2 empty result slots", summary["stages"][1]["detail"])
        self.assertIn("1 values, 1 series", summary["stages"][3]["detail"])
        self.assertIn("impact 9.1", summary["stages"][4]["detail"])

    def test_a_draft_that_forgot_a_slot_does_not_count_as_a_draft(self):
        real = stages.BY_ID["S2"]["driver"]

        def forgetful(project, source, context):
            real(project, source, context)
            (pathlib.Path(project) / "2_paper" / "paper.tex").write_text(
                ORIGINAL_TEX.replace("Gain is 1.5 points", "Gain is \\PFVAL{acc}"), encoding="utf-8")

        stages.BY_ID["S2"]["driver"] = forgetful
        self.addCleanup(stages.BY_ID["S2"].__setitem__, "driver", real)
        summary = Orchestrator(self.project, {}).run()
        self.assertEqual(summary["blocked"]["stage"], "S2")
        self.assertIn("curve", summary["blocked"]["reason"])

    def test_results_that_miss_a_slot_do_not_pass_the_code_stage(self):
        partial = {"schema_version": 1, "values": {"acc": 0.9}}
        real = stages.BY_ID["S4"]["driver"]

        def partial_driver(project, source, context):
            target = pathlib.Path(project) / "4_code" / "results.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(partial), encoding="utf-8")

        stages.BY_ID["S4"]["driver"] = partial_driver
        self.addCleanup(stages.BY_ID["S4"].__setitem__, "driver", real)
        summary = Orchestrator(self.project, {}).run()
        self.assertEqual(summary["blocked"]["stage"], "S4")
        self.assertIn("curve", summary["blocked"]["reason"])
        self.assertEqual(summary["state"], "REVIEWED")

    def test_a_blocked_code_stage_stops_before_refine(self):
        def broken(project, source, context):
            raise ValueError("docker is installed but its daemon is not running")
        real = stages.BY_ID["S4"]["driver"]
        stages.BY_ID["S4"]["driver"] = broken
        self.addCleanup(stages.BY_ID["S4"].__setitem__, "driver", real)
        summary = Orchestrator(self.project, {}).run()
        self.assertEqual(summary["blocked"]["stage"], "S4")
        self.assertNotIn("5_refine/report.json", self.order)

    def test_resume_skips_done_stages_but_not_ones_edited_since(self):
        Orchestrator(self.project, {}).run()
        again = Orchestrator(self.project, {}).run(resume=True)
        self.assertEqual([s["status"] for s in again["stages"]], ["SKIPPED"] * 5)
        (self.project / "1_idea" / "idea.md").write_text("# edited\n", encoding="utf-8")
        edited = Orchestrator(self.project, {}).run(resume=True)
        self.assertEqual(edited["stages"][0]["status"], "PASS")

    def test_stages_run_in_separate_invocations_are_all_remembered_by_resume(self):
        Orchestrator(self.project, {}).run("S1", "S2")
        Orchestrator(self.project, {}).run("S3", "S3")
        again = Orchestrator(self.project, {}).run(resume=True)
        self.assertEqual([s["status"] for s in again["stages"]],
                         ["SKIPPED", "SKIPPED", "SKIPPED", "PASS", "PASS"])

    def test_stage_range_is_validated(self):
        with self.assertRaises(ValueError):
            stages.ordered("S3", "S1")
        with self.assertRaises(ValueError):
            stages.ordered("S9")


if __name__ == "__main__":
    unittest.main()
