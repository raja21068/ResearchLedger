"""The results contract: empty slots in the draft, filled by code, never by a model."""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory import results  # noqa: E402
from factory.steps.review import compile_pdf, pdf_text  # noqa: E402

SPEC = {"slots": [
    {"id": "main_acc", "kind": "value", "describe": "accuracy of our method"},
    {"id": "base_acc", "kind": "value", "describe": "accuracy of the baseline"},
    {"id": "loss_curve", "kind": "series", "describe": "training loss", "plot": "line",
     "x_label": "epoch", "y_label": "loss"},
    {"id": "extra", "kind": "value", "describe": "optional extra", "optional": True}]}

DRAFT = (
    "\\documentclass{article}\n\\begin{document}\n"
    "\\begin{tabular}{ll}Method & Accuracy\\\\ Ours & \\PFVAL{main_acc}\\\\ "
    "Baseline & \\PFVAL{base_acc}\\\\ Extra & \\PFVAL{extra}\\end{tabular}\n\n"
    "\\begin{figure}\\PFFIG{loss_curve}\\caption{Training loss.}\\end{figure}\n"
    "\\end{document}\n")


class SpecTests(unittest.TestCase):
    def test_valid_spec_has_no_problems(self):
        self.assertEqual(results.validate_spec(SPEC), [])

    def test_bad_ids_kinds_and_duplicates_are_reported(self):
        bad = {"slots": [{"id": "9bad", "kind": "value", "describe": "x"},
                         {"id": "ok_id", "kind": "weird", "describe": "x"},
                         {"id": "ok_id", "kind": "value", "describe": ""}]}
        problems = " | ".join(results.validate_spec(bad))
        self.assertIn("bad slot id", problems)
        self.assertIn("kind must be", problems)
        self.assertIn("duplicate", problems)
        self.assertIn("describe", problems)
        self.assertTrue(results.validate_spec({"slots": []}))

    def test_draft_coverage_finds_forgotten_and_invented_slots(self):
        self.assertEqual(results.coverage_problems(DRAFT, SPEC), [])
        forgot = DRAFT.replace("\\PFVAL{base_acc}", "0.5")
        self.assertIn("base_acc", " ".join(results.coverage_problems(forgot, SPEC)))
        invented = DRAFT.replace("\\PFVAL{main_acc}", "\\PFVAL{main_acc}\\PFVAL{made_up}")
        self.assertIn("made_up", " ".join(results.coverage_problems(invented, SPEC)))

    def test_macros_are_added_once_before_begin_document(self):
        once = results.ensure_macros(DRAFT)
        self.assertEqual(once.count(results.MARKER), 1)
        self.assertEqual(results.ensure_macros(once), once)
        self.assertLess(once.index("\\newcommand{\\PFVAL}"), once.index("\\begin{document}"))
        self.assertIn("graphicx", once)


class ResultsFileTests(unittest.TestCase):
    def write(self, payload):
        path = pathlib.Path(tempfile.mkdtemp(prefix="pf-res-")) / "results.json"
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_good_results_load_and_missing_required_slots_are_named(self):
        good = {"values": {"main_acc": 0.9}, "series": {
            "loss_curve": {"x": [1, 2], "series": {"a": [1.0, 0.5]}}}}
        payload = results.read_results(self.write(good))
        self.assertEqual(results.missing_slots(SPEC, payload), ["base_acc"])  # extra is optional
        good["values"]["base_acc"] = 0.8
        self.assertEqual(results.missing_slots(SPEC, results.read_results(self.write(good))), [])

    def test_only_real_numbers_and_aligned_series_are_accepted(self):
        for bad in ({"values": {"a": True}}, {"values": {"a": "0.9"}},
                    {"values": {"a": float("nan")}}, {"values": {"a": float("inf")}},
                    {"series": {"s": {"x": [1, 2], "series": {"a": [1]}}}},
                    {"series": {"s": {"x": [], "series": {"a": []}}}}, {}, []):
            with self.assertRaises(ValueError, msg=str(bad)):
                results.read_results(self.write(bad))

    def test_number_formatting(self):
        self.assertEqual(results.format_value(12), "12")
        self.assertEqual(results.format_value(0.912345), "0.9123")
        self.assertEqual(results.format_value(0.0000123), "$1.23\\times10^{-5}$")


@unittest.skipUnless(shutil.which("pdflatex"), "pdflatex not installed")
class EmptyDraftThenFillTests(unittest.TestCase):
    """The real thing: the draft compiles with empty slots, and code fills them."""

    def setUp(self):
        self.build = pathlib.Path(tempfile.mkdtemp(prefix="pf-fill-"))
        self.addCleanup(shutil.rmtree, self.build, ignore_errors=True)
        (self.build / "paper.tex").write_text(results.ensure_macros(DRAFT), encoding="utf-8")

    def text(self):
        return pdf_text(compile_pdf(self.build, "paper.tex")).replace("\n", " ")

    def test_empty_draft_compiles_with_dashes_and_pending_figures(self):
        text = self.text()
        self.assertIn("Figure pending", text)
        self.assertNotIn("0.9", text)
        self.assertIn("Ours", text)

    def test_filling_puts_measured_numbers_and_a_real_plot_into_the_paper(self):
        payload = {"values": {"main_acc": 0.9123, "base_acc": 0.85},
                   "series": {"loss_curve": {"x": [1, 2, 3], "series": {"ours": [1.0, 0.6, 0.4]}}}}
        filled = results.fill(self.build, SPEC, payload)
        self.assertEqual(filled["values"], 2)
        self.assertEqual(filled["figures"], ["loss_curve"])
        self.assertTrue((self.build / "figures" / "loss_curve.pdf").is_file())
        text = self.text()
        self.assertIn("0.9123", text)
        self.assertIn("0.85", text)
        self.assertNotIn("Figure pending", text)  # the plot replaced the placeholder


if __name__ == "__main__":
    unittest.main()
