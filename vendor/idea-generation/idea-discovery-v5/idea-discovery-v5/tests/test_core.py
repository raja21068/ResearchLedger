import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from utils import ClaudeClient
from schema_validator import validate_json, validate_semantics
from step1b_source_verify import title_similarity, DOI_RE, evidence_grade
from step7_report import _novelty_verdict, _novelty_score
from step7_attack_loop import validate_scorecard, evaluate_round, run_attack_loop
from step1b_source_verify import domain_profile
from step4b_discovery_grounding import solution_level_is_eligible, _validate_solution_evidence
from step5_evolution import eligible_gap_ids, run_idea_evolution
from step7b_survivor_elo import greenlight_survivors, elo_update, run_survivor_elo
from ideation_memory import select_relevant_memory, update_memory


class JsonParsingTests(unittest.TestCase):
    def test_fenced_json_parses(self):
        x = ClaudeClient._parse_json_payload('```json\n{"a": 1}\n```')
        self.assertEqual(x, {"a": 1})

    def test_surrounding_text_parses(self):
        x = ClaudeClient._parse_json_payload('Result follows:\n{"a": [1,2]}\nThanks')
        self.assertEqual(x["a"], [1, 2])


class SchemaTests(unittest.TestCase):
    def test_valid_paper_record(self):
        record = {
            "paper_id":"smith-2026", "title":"A Study", "authors":["A Smith"], "year":2026,
            "venue":"X", "problem":{"statement":"p"},
            "method":{"name":"m","category":"other","mechanism":"how"},
            "datasets":[], "metrics":[], "claims":[],
            "limitations":{"acknowledged":[],"inferred":["small sample"]},
            "reproducibility":{}, "extraction_confidence":"high"
        }
        errs = validate_json(record, ROOT / "schemas" / "paper_record.schema.json", raise_on_error=False)
        self.assertEqual(errs, [])
        self.assertEqual(validate_semantics("paper_record", record), [])

    def test_gap_priority_invariant(self):
        obj={"gaps":[{"gap_id":"GAP-1","evidence":{"source":"x"},"scoring":{"impact":3,"feasibility":2,"novelty":3,"priority_score":17}}]}
        issues=validate_semantics("gap_analysis",obj)
        self.assertTrue(any("!= 18" in x for x in issues))


class VerificationTests(unittest.TestCase):
    def test_title_similarity(self):
        self.assertGreater(title_similarity("Deep Learning for X", "Deep learning for X"), 0.95)
        self.assertLess(title_similarity("Deep Learning for X", "Unrelated Chemistry Study"), 0.5)

    def test_doi_format(self):
        self.assertTrue(DOI_RE.match("10.1000/xyz123"))
        self.assertFalse(DOI_RE.match("doi:xyz"))

    def test_cs_evidence_profile(self):
        p={"claims":[{"evidence_type":"empirical"},{"evidence_type":"ablation"}],"reproducibility":{"code_available":True,"data_available":True},"method":{"category":"transformer"}}
        grade=evidence_grade(p,"computer_science_ai")
        self.assertIn("empirical + ablation", grade["evidence_characterization"])

    def test_domain_profile_detects_ai(self):
        corpus={"papers":[{"method":{"category":"transformer"}},{"method":{"category":"cnn"}},{"method":{"category":"other"}}]}
        self.assertEqual(domain_profile(corpus), "computer_science_ai")


class CompatibilityTests(unittest.TestCase):
    def test_novelty_new_structure(self):
        v={"consensus":{"verdict":"PROCEED","novelty_score":8.2}}
        self.assertEqual(_novelty_verdict(v), "PROCEED")
        self.assertEqual(_novelty_score(v), 8.2)

    def test_novelty_legacy_structure(self):
        v={"overall_assessment":{"verdict":"PIVOT","novelty_score":4}}
        self.assertEqual(_novelty_verdict(v), "PIVOT")
        self.assertEqual(_novelty_score(v), 4)

    def test_scorecard_arithmetic(self):
        rows = [
            ("Problem importance",15,12),("Evidence that the gap exists",15,12),
            ("Novelty vs. recent literature",20,16),("Scientific insight",15,12),
            ("Experimental feasibility",10,8),("Potential impact",10,8),
            ("Evaluation strength possible",10,8),("Reproducibility",5,4),
        ]
        s={"criteria":[{"criterion":n,"weight":w,"score":v,"rationale":"x"} for n,w,v in rows],"total_score":80}
        self.assertEqual(validate_scorecard(s), [])

    def test_loop_requires_all_checks_same_round(self):
        rows = [
            ("Problem importance",15,12),("Evidence that the gap exists",15,12),
            ("Novelty vs. recent literature",20,16),("Scientific insight",15,12),
            ("Experimental feasibility",10,8),("Potential impact",10,8),
            ("Evaluation strength possible",10,8),("Reproducibility",5,4),
        ]
        scorecard={"criteria":[{"criterion":n,"weight":w,"score":v} for n,w,v in rows],"total_score":80}
        novelty={"verdict":"SURVIVES","patent_relevance":"LOW","search_coverage":{"patents_when_relevant":"NOT_RELEVANT"}}
        matrix={"verdict":"DISTINCT","intellectual_contribution":"new explanatory principle"}
        reviewer={"verdict":"SURVIVES","criticisms":[{"severity":"Major"}]}
        ev=evaluate_round(scorecard,novelty,matrix,reviewer,{"greenlight_score":80,"min_novelty_component":14})
        self.assertEqual(ev["decision"],"GREENLIGHT")

        matrix["verdict"]="WEAK_DELTA"
        ev=evaluate_round(scorecard,novelty,matrix,reviewer,{"greenlight_score":80,"min_novelty_component":14})
        self.assertEqual(ev["decision"],"REVISE")

    def test_direct_collision_blocks_greenlight(self):
        rows = [
            ("Problem importance",15,15),("Evidence that the gap exists",15,15),
            ("Novelty vs. recent literature",20,20),("Scientific insight",15,15),
            ("Experimental feasibility",10,10),("Potential impact",10,10),
            ("Evaluation strength possible",10,10),("Reproducibility",5,5),
        ]
        scorecard={"criteria":[{"criterion":n,"weight":w,"score":v} for n,w,v in rows],"total_score":100}
        novelty={"verdict":"KILL","direct_collision":True,"patent_relevance":"LOW","search_coverage":{"patents_when_relevant":"NOT_RELEVANT"}}
        matrix={"verdict":"NOT_NOVEL","intellectual_contribution":""}
        reviewer={"verdict":"KILL","criticisms":[{"severity":"Fatal"}]}
        ev=evaluate_round(scorecard,novelty,matrix,reviewer,{"greenlight_score":80,"min_novelty_component":14})
        self.assertEqual(ev["decision"],"KILL_OR_PIVOT")



class IterativeLoopExecutionTests(unittest.TestCase):
    def test_revision_restarts_phase10_and_can_greenlight_round2(self):
        valid_rows_round1 = [
            ("Problem importance",15,12),("Evidence that the gap exists",15,10),
            ("Novelty vs. recent literature",20,10),("Scientific insight",15,10),
            ("Experimental feasibility",10,8),("Potential impact",10,8),
            ("Evaluation strength possible",10,8),("Reproducibility",5,4),
        ]
        valid_rows_round2 = [
            ("Problem importance",15,13),("Evidence that the gap exists",15,13),
            ("Novelty vs. recent literature",20,17),("Scientific insight",15,13),
            ("Experimental feasibility",10,8),("Potential impact",10,8),
            ("Evaluation strength possible",10,8),("Reproducibility",5,4),
        ]

        score1={"idea_id":"I1","criteria":[{"criterion":n,"weight":w,"score":v,"rationale":"x"} for n,w,v in valid_rows_round1],
                "total_score":70,"strongest_aspects":[],"major_weaknesses":["weak novelty"],"novelty_check":{},
                "evidence_needed":[],"how_to_improve":[],"final_assessment":"","blocking_issues":["weak novelty"]}
        novel1={"idea_id":"I1","search_coverage":{"patents_when_relevant":"NOT_RELEVANT"},"papers_that_threaten_novelty":[],
                "direct_collision":False,"strongest_collision":"","patent_relevance":"LOW","unresolved_search_gaps":[],
                "verdict":"REVISE","reason":"delta too weak"}
        matrix1={"idea_id":"I1","competitors":[],"features":[],"matrix":[],"already_covered":[],"genuinely_novel":[],
                 "closest_competing_paper":"P","novelty_type":"new_combination","intellectual_contribution":"weak",
                 "checkmark_warning":"not count","verdict":"WEAK_DELTA","reason":"weak"}
        reviewer1={"idea_id":"I1","criticisms":[{"rank":i,"criticism":"c","severity":"Major","why":"x","fix_before_coding":"fix"} for i in range(1,11)],
                   "fatal_flaws_to_fix_before_coding":[],"major_flaws_to_fix_before_coding":["fix"],
                   "strongest_rejection_case":"incremental","verdict":"REVISE","reason":"revise"}
        revision1={"idea_id":"I1","decision":"REVISE","reason":"pivot","revised_idea":{
                    "idea_id":"I1","source_gap":"G1","title":"Revised","hypothesis":{"statement":"H2","null_hypothesis":"N2"},
                    "method_sketch":{},"experiment_design":{},"expected_outcomes":{},"scoring":{}},
                   "change_log":[{"source_phase":"11","issue":"weak","change":"mechanistic pivot","why_this_is_non_cosmetic":"new hypothesis"}],
                   "unresolved_issues":[],"is_scientific_pivot":True,"pivot_description":"mechanistic pivot"}

        score2={"idea_id":"I1","criteria":[{"criterion":n,"weight":w,"score":v,"rationale":"x"} for n,w,v in valid_rows_round2],
                "total_score":84,"strongest_aspects":[],"major_weaknesses":[],"novelty_check":{},
                "evidence_needed":[],"how_to_improve":[],"final_assessment":"","blocking_issues":[]}
        novel2={"idea_id":"I1","search_coverage":{"patents_when_relevant":"NOT_RELEVANT"},"papers_that_threaten_novelty":[],
                "direct_collision":False,"strongest_collision":"","patent_relevance":"LOW","unresolved_search_gaps":[],
                "verdict":"SURVIVES","reason":"distinct"}
        matrix2={"idea_id":"I1","competitors":[],"features":[],"matrix":[],"already_covered":[],"genuinely_novel":["mechanism"],
                 "closest_competing_paper":"P","novelty_type":"conceptual","intellectual_contribution":"new explanatory mechanism",
                 "checkmark_warning":"not count","verdict":"DISTINCT","reason":"distinct"}
        reviewer2={"idea_id":"I1","criticisms":[{"rank":i,"criticism":"c","severity":"Minor","why":"x","fix_before_coding":""} for i in range(1,11)],
                   "fatal_flaws_to_fix_before_coding":[],"major_flaws_to_fix_before_coding":[],
                   "strongest_rejection_case":"none fatal","verdict":"SURVIVES","reason":"survives"}

        responses=[score1,novel1,matrix1,reviewer1,revision1,score2,novel2,matrix2,reviewer2]

        class FakeAttack:
            actual_provider="fake-independent"
            def __init__(self, config): self.responses=list(responses)
            def ask_json(self, system, user, temperature=0.0):
                return self.responses.pop(0)

        class FakeClaude:
            def __init__(self, config=None): pass

        fake_search={"core_claims":["c"],"query_plan":[],"queries_used":["q"],
                     "semantic_scholar_results":[],"arxiv_results":[],"openalex_results":[],
                     "recent_concurrent_results":[],"total_unique_papers_found":0}

        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            (out/"idea_report.json").write_text(json.dumps({"ideas":[{
                "idea_id":"I1","source_gap":"G1","title":"Original",
                "hypothesis":{"statement":"H1","null_hypothesis":"N1"},
                "method_sketch":{},"experiment_design":{},"expected_outcomes":{},"scoring":{}
            }]}), encoding="utf-8")
            config={"pipeline":{"output_dir":td},"attack_loop":{"enabled":True,"max_rounds":3,"greenlight_score":80,"min_novelty_component":14},
                    "citation_expansion":{"enabled":False}}
            with patch("step7_attack_loop.AttackClient", FakeAttack), \
                 patch("step7_attack_loop.ClaudeClient", FakeClaude), \
                 patch("step7_attack_loop.run_literature_search", return_value=fake_search):
                result=run_attack_loop(config)
            self.assertEqual(result["ideas"][0]["final_decision"],"GREENLIGHT")
            self.assertEqual(result["ideas"][0]["rounds_run"],2)
            self.assertEqual(result["ideas"][0]["final_idea"]["title"],"Revised")
            self.assertTrue((out/"attack_loop"/"I1"/"round_02"/"phase13_reviewer_attack.json").exists())


class V4DiscoveryTests(unittest.TestCase):
    def test_solution_levels_1_2_block_and_3_4_proceed(self):
        self.assertFalse(solution_level_is_eligible(1))
        self.assertFalse(solution_level_is_eligible(2))
        self.assertTrue(solution_level_is_eligible(3))
        self.assertTrue(solution_level_is_eligible(4))

    def test_quote_or_zero_evidence_validation(self):
        pool=[{"title":"Paper A","abstract":"Our method fails under severe domain shift and calibration degrades."}]
        fmap={"gap_solution_checks":[{"gap_id":"G1","level":3,"action":"PROCEED","confidence":"HIGH","evidence":[
            {"paper_title":"Paper A","quote":"fails under severe domain shift"},
            {"paper_title":"Made Up","quote":"something"}
        ]}],"coverage_limitations":[]}
        out=_validate_solution_evidence(fmap,pool,[{"gap_id":"G1"},{"gap_id":"G2"}])
        rows={x["gap_id"]:x for x in out["gap_solution_checks"]}
        self.assertEqual(len(rows["G1"]["evidence"]),1)
        self.assertEqual(rows["G1"]["evidence_titles"],["Paper A"])
        self.assertEqual(rows["G2"]["level"],0)
        self.assertEqual(rows["G2"]["action"],"SWITCH")

    def test_eligible_gap_filter_is_fail_closed(self):
        d={"map":{"gap_solution_checks":[
            {"gap_id":"G1","level":1,"action":"SWITCH"},
            {"gap_id":"G2","level":2,"action":"SWITCH"},
            {"gap_id":"G3","level":3,"action":"PROCEED"},
            {"gap_id":"G4","level":4,"action":"PROCEED"},
            {"gap_id":"G5","level":3,"action":"SWITCH"},
        ]}}
        self.assertEqual(eligible_gap_ids(d,True), {"G3","G4"})

    def test_survivor_elo_never_admits_non_greenlight(self):
        a={"ideas":[
            {"final_decision":"GREENLIGHT","rounds_run":2,"final_idea":{"idea_id":"I1","title":"A"}},
            {"final_decision":"KILL","rounds_run":1,"final_idea":{"idea_id":"I2","title":"B"}},
            {"final_decision":"KILL_MAX_ROUNDS","rounds_run":4,"final_idea":{"idea_id":"I3","title":"C"}},
        ]}
        s=greenlight_survivors(a)
        self.assertEqual([x["idea_id"] for x in s],["I1"])

    def test_elo_update_is_zero_sum(self):
        a,b=elo_update(1500,1500,1.0,32)
        self.assertAlmostEqual(a,1516.0,places=6)
        self.assertAlmostEqual(b,1484.0,places=6)
        self.assertAlmostEqual(a+b,3000.0,places=6)

    def test_cross_run_memory_records_survival_and_dead_end(self):
        with tempfile.TemporaryDirectory() as td:
            cfg={"ideation_memory":{"enabled":True,"path":str(Path(td)/"memory.json"),"max_entries":10,"top_k_relevant":2}}
            attacks={"ideas":[
                {"idea_id":"I1","final_decision":"GREENLIGHT","rounds_run":2,"final_idea":{"idea_id":"I1","title":"Causal fusion","source_gap":"G1","gap_type":"VOID","contribution_type":"method","method_sketch":{"key_components":["causal","fusion"],"approach":"causal fusion"},"positioning":{"contribution_sentence":"new causal fusion"}}},
                {"idea_id":"I2","final_decision":"KILL","rounds_run":1,"final_title":"Old trick","final_blockers":["direct collision: already published"]}
            ]}
            elo={"ranking":[{"idea_id":"I1","rank":1,"rating":1516}]}
            m=update_memory(cfg,attacks,elo)
            by={x["idea_id"]:x for x in m["entries"]}
            self.assertEqual(by["I1"]["status"],"FEASIBLE")
            self.assertEqual(by["I1"]["elo_rank"],1)
            self.assertEqual(by["I2"]["failure_class"],"FUNDAMENTAL")
            rel=select_relevant_memory(cfg,"causal fusion models")
            self.assertEqual(rel[0]["idea_id"],"I1")


class V4StageExecutionTests(unittest.TestCase):
    @staticmethod
    def _idea(title="Seed"):
        return {
            "idea_id":"IDEA-001","source_gap":"G1","gap_type":"VOID","title":title,"research_direction":"R1",
            "hypothesis":{"statement":"If X then Y because Z","null_hypothesis":"X does not change Y","expected_direction":"positive"},
            "method_sketch":{"approach":"test mechanism","key_components":["X"],"baselines":["B"],"ablations":["remove X"]},
            "experiment_design":{"datasets":["D"],"metrics":["M"],"evaluation_protocol":"controlled","minimum_viable_experiment":"small test"},
            "feasibility":{"compute_estimate":"10 GPU-hours","data_requirements":"public","implementation_complexity":"weeks","dependencies":[]},
            "expected_outcomes":{"if_positive":"supports mechanism","if_negative":"rules out mechanism","either_way_value":"clarifies boundary"},
            "contribution_type":"method",
            "risk_assessment":{"risk_level":"MEDIUM","main_risk":"weak effect","mitigation":"power study","reviewer_objection":"incremental"},
            "positioning":{"closest_work":"P","differentiation":"mechanism","target_venue":"Q1","contribution_sentence":"new mechanism"},
            "scoring":{"gap_importance":4,"scientific_rigor":4,"feasibility":4,"either_way_value":4,"novelty_potential":4,"weighted_score":4.0},
        }

    def test_three_persona_evolution_executes_all_iterations(self):
        seed=self._idea("Seed")
        responses=[{"ideas":[seed],"rejected_directions":[]}]
        for i,persona in enumerate(["innovator","critic","pragmatist"],1):
            selected=self._idea(f"Round {i}")
            variants={"innovator":self._idea(f"I{i}"),"pragmatist":self._idea(f"P{i}"),"critic":self._idea(f"C{i}")}
            responses.append({"iteration":i,"evaluation":{"novelty":"x","feasibility":"x","impact":"x","alignment":"x","coherence":"x","main_failure_mode":"x"},"variants":variants,"selected_persona":persona,"selection_reason":"best","selected_idea":selected,"pivoted":False})

        class FakeClaude:
            def __init__(self, config=None): self.responses=list(responses)
            def ask_json(self, system, user, temperature=0.0): return self.responses.pop(0)

        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            (out/"discovery_grounding.json").write_text(json.dumps({"coverage":{"paper_count":30,"target_min":30},"map":{"gap_solution_checks":[{"gap_id":"G1","level":3,"action":"PROCEED"}]} }),encoding="utf-8")
            (out/"gap_analysis.json").write_text(json.dumps({"gaps":[{"gap_id":"G1","gap_type":"VOID","description":"gap","scoring":{"priority_score":18}}]}),encoding="utf-8")
            cfg={"pipeline":{"output_dir":td},"discovery_grounding":{"fail_closed_under_min_papers":True,"require_solution_level_3_or_4":True,"fail_closed_if_no_eligible_gap":True},"idea_evolution":{"directions":1,"iterations":3,"use_ideation_memory":False}}
            with patch("step5_evolution.ClaudeClient",FakeClaude):
                result=run_idea_evolution(cfg)
            self.assertEqual(len(result["ideas"]),1)
            self.assertEqual(result["ideas"][0]["title"],"Round 3")
            trace=json.loads((out/"evolution_trace.json").read_text())
            self.assertEqual(len(trace["tracks"][0]["rounds"]),3)
            self.assertEqual(result["ideas"][0]["_evolution_personas"],["innovator","critic","pragmatist"])

    def test_survivor_elo_stage_ranks_only_greenlights(self):
        class FakeAttack:
            actual_provider="fake"
            def __init__(self, config): pass
            def ask_json(self, system, user, temperature=0.0):
                return {"idea_a":{"novelty":9,"feasibility":8,"relevance":9,"clarity":8,"rationale":"A"},"idea_b":{"novelty":7,"feasibility":8,"relevance":8,"clarity":8,"rationale":"B"},"winner":"A","reason":"A stronger"}
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            attacks={"ideas":[
                {"idea_id":"I1","final_decision":"GREENLIGHT","rounds_run":2,"final_idea":{"idea_id":"I1","title":"A"}},
                {"idea_id":"I2","final_decision":"GREENLIGHT","rounds_run":1,"final_idea":{"idea_id":"I2","title":"B"}},
                {"idea_id":"I3","final_decision":"KILL","rounds_run":1,"final_idea":{"idea_id":"I3","title":"C"}},
            ]}
            (out/"attack_loop_summary.json").write_text(json.dumps(attacks),encoding="utf-8")
            cfg={"pipeline":{"output_dir":td},"survivor_elo":{"enabled":True,"starting_rating":1500,"k_factor":32}}
            with patch("step7b_survivor_elo.AttackClient",FakeAttack):
                result=run_survivor_elo(cfg)
            self.assertEqual([x["idea_id"] for x in result["ranking"]],["I1","I2"])
            self.assertEqual(result["ranking"][0]["rank"],1)
            self.assertGreater(result["ranking"][0]["rating"],result["ranking"][1]["rating"])


if __name__ == "__main__":
    unittest.main()
