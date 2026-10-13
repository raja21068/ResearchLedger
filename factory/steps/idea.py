"""Step 1 -- idea generation and verification.

Generation happens upstream (EvoSci); this module is the gate. It takes the
candidate ideas EvoSci produced, applies the hard falsifiability constraint,
ranks the survivors by reviewer score, and writes the winner out as `idea.md`,
the input PaperOrchestra needs.

Falsifiability is a constraint, not a score. An idea that cannot name the exact
result that would disprove it is rejected outright, however well it scores.
"""
import datetime
import json
import math
import pathlib

from factory.io import atomic_json, atomic_text

SCORE_FIELDS = ("novelty", "importance", "feasibility", "falsifiability", "evidence_fit")
FALSIFIER_FIELDS = ("statement", "metric", "threshold")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def falsifier_problems(idea):
    """Why this idea's falsifier does not count, or an empty list if it does.

    The falsifier must be an object naming the observable (`metric`), the value
    that would disprove the hypothesis (`threshold`) and a one-sentence
    `statement` of that result. A free-text "it would fail if it doesn't work"
    does not name a result and is refused.
    """
    falsifier = idea.get("falsifier")
    if not isinstance(falsifier, dict):
        return ["falsifier must be an object with statement, metric and threshold"]
    problems = [f"falsifier.{field} is missing" for field in FALSIFIER_FIELDS
                if falsifier.get(field) in (None, "")]
    if "threshold" not in falsifier or isinstance(falsifier["threshold"], bool) \
            or not isinstance(falsifier.get("threshold"), (int, float)) \
            or not math.isfinite(falsifier["threshold"]):
        problems.append("falsifier.threshold must be a number")
    statement = str(falsifier.get("statement", "")).strip()
    if statement and len(statement.split()) < 5:
        problems.append("falsifier.statement is too short to name a result")
    return problems


def score(idea):
    reviews = idea.get("reviews", [])
    if not isinstance(reviews, list) or len(reviews) < 2 or any(not isinstance(r, dict) for r in reviews):
        raise ValueError(f"idea {idea['id']} needs at least two independent reviews")
    reviewers = [review.get("reviewer_id") for review in reviews]
    if any(not isinstance(r, str) or not r.strip() for r in reviewers) or len(set(reviewers)) != len(reviewers):
        raise ValueError(f"idea {idea['id']} has missing or duplicate reviewers")
    components = {}
    for field in SCORE_FIELDS:
        values = [review.get(field) for review in reviews]
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 10
               for v in values):
            raise ValueError(f"idea {idea['id']} has invalid {field} score")
        components[field] = round(sum(values) / len(values), 3)
    return components, round(sum(components.values()) / len(SCORE_FIELDS), 3)


def select(project, source):
    """Gate, rank and write the winning idea. Raises ValueError if none survives."""
    project, source = pathlib.Path(project), pathlib.Path(source)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(payload, (dict, list)):
        raise ValueError("ideas input must be an object with an ideas list, or a list")
    ideas = payload.get("ideas", []) if isinstance(payload, dict) else payload
    if not isinstance(ideas, list):
        raise ValueError("ideas must be a JSON list")
    if len(ideas) < 2:
        raise ValueError("need at least two candidate ideas to select between")
    ranked, rejected, seen = [], [], set()
    for idea in ideas:
        if not isinstance(idea, dict):
            raise ValueError("each candidate idea must be a JSON object")
        if (not isinstance(idea.get("id"), str) or not idea["id"].strip() or
                len(idea["id"]) > 100):
            raise ValueError("idea id must be a non-empty string of at most 100 characters")
        missing = [f for f in ("id", "title", "hypothesis")
                   if not isinstance(idea.get(f), str) or not idea[f].strip()]
        if missing:
            raise ValueError(f"idea missing non-empty fields: {', '.join(missing)}")
        if idea["id"] in seen:
            raise ValueError(f"duplicate idea id: {idea['id']}")
        seen.add(idea["id"])
        problems = falsifier_problems(idea)
        if problems:
            rejected.append({"id": idea["id"], "title": idea["title"], "reasons": problems})
            continue
        components, total = score(idea)
        ranked.append({**idea, "score_components": components, "aggregate_score": total})
    if not ranked:
        raise ValueError("every idea failed the falsifiability gate: " +
                         "; ".join(f"{r['id']}: {', '.join(r['reasons'])}" for r in rejected))
    ranked.sort(key=lambda idea: (-idea["aggregate_score"], idea["id"]))
    winner = ranked[0]
    report = {"schema_version": 1, "run_at": now(), "score_scale": "0-10",
              "aggregation": "unweighted mean of reviewer means",
              "winner": winner["id"], "ideas": ranked, "rejected_unfalsifiable": rejected}
    out = project / "1_idea"
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(out / "tournament.json", report)
    falsifier = winner["falsifier"]
    lines = [f"# {winner['title']}", "", "## Hypothesis", "", winner["hypothesis"], "",
             "## Falsifier", "", falsifier["statement"], "",
             f"Metric: `{falsifier['metric']}`; disproved at threshold {falsifier['threshold']}.", ""]
    if winner.get("method"):
        lines += ["## Method", "", winner["method"], ""]
    lines += ["## Selection", "",
              f"Selected from {len(ranked)} falsifiable ideas ({len(rejected)} rejected as "
              f"unfalsifiable) with an aggregate reviewer score of {winner['aggregate_score']} "
              f"on a 0-10 scale.", "",
              "| criterion | mean score |", "|---|---:|"]
    lines += [f"| {name} | {value} |" for name, value in sorted(winner["score_components"].items())]
    lines += ["", "## Ideas not selected", ""]
    lines += [f"- {idea['id']}: {idea['title']} ({idea['aggregate_score']})" for idea in ranked[1:]]
    atomic_text(out / "idea.md", "\n".join(lines) + "\n")
    return report


def select_v5(project):
    """Select a single explicitly adopted V5 survivor without fictitious rankings."""
    from factory.integrations.idea_discovery import ARCHIVE, DISTRIBUTION
    from factory.pipeline.provenance import hash_file
    project = pathlib.Path(project)
    record_path = project / '_inputs' / 'v5_adoption.json'
    record = json.loads(record_path.read_text(encoding='utf-8'))
    source = project / '_vendor' / DISTRIBUTION / 'output' / 'falsification_summary.json'
    if (not source.is_file() or record.get('source_report_sha256') != hash_file(source) or
            record.get('source_archive_sha256') != hash_file(ARCHIVE) or
            record.get('operator_acknowledged') is not True):
        raise ValueError('V5 adoption source changed, or required provenance/acknowledgement missing')
    matches = [row for row in json.loads(source.read_text(encoding='utf-8')).get('ideas', [])
               if isinstance(row, dict) and row.get('idea_id') == record.get('selected_id')]
    if len(matches) != 1 or matches[0].get('final_decision') != record.get('v5_decision'):
        raise ValueError('V5 adoption status/ID no longer matches the original source')
    original = matches[0].get('final_idea', {})
    payload = record.get('idea')
    if (not isinstance(original, dict) or not isinstance(payload, dict) or
            payload.get('title') != original.get('title') or
            payload.get('hypothesis') != (original.get('hypothesis') or {}).get('statement') or
            payload.get('method') != json.dumps(original.get('method_sketch', {}), ensure_ascii=False)):
        raise ValueError('V5 adopted idea content differs from the source survivor')
    if not isinstance(payload, dict) or not all(isinstance(payload.get(x), str) and payload[x].strip()
                                                for x in ('id','title','hypothesis','method')):
        raise ValueError('V5 adoption missing essential idea fields')
    if record.get('v5_decision') not in {'READY_FOR_MVE', 'GREENLIGHT'}:
        raise ValueError('V5 adoption cannot select a failed idea')
    errors = falsifier_problems(payload)
    if errors:
        raise ValueError('V5 adoption requires a measurable falsifier: '+ '; '.join(errors))
    out = project / '1_idea'
    out.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'run_at': now(), 'winner': payload['id'],
              'source': 'IDEA_DISCOVERY_V5_EXPLICIT_OPERATOR_ADOPTION',
              'v5_decision': record['v5_decision'], 'ideas': [payload],
              'rejected_unfalsifiable': [], 'aggregate_score': None,
              'caveat': 'No numeric peer-review ranking was fabricated. '
                        'V5 output does not certify independent novelty or experimental correctness.'}
    atomic_json(out / 'tournament.json', report)
    f = payload['falsifier']
    atomic_text(out / 'idea.md', '\n'.join([
        '# '+payload['title'],'','## Hypothesis','',payload['hypothesis'],'',
        '## Falsifier','',f['statement'],'',f"Metric: `{f['metric']}`; rejection threshold {f['threshold']}.",'',
        '## Method','',payload['method'],'',
        '## Source','',f"Adopted from Idea Discovery V5: {record['v5_decision']}.",
        'Numeric falsifier supplied and acknowledged by the operator.',
        'No independent verification of novelty or scientific correctness is implied.','']))
    return report


# -- generation from a topic (no ideas.json supplied) ------------------------

ASSETS = pathlib.Path(__file__).resolve().parent / "review_assets"
PERSONAS = {
    "novelty-skeptic": "You know the literature well and are hostile to incremental work. Score "
                       "novelty and importance harshly; an idea that is a small variation on "
                       "known work scores 3 or below.",
    "methods-realist": "You judge whether the idea can be tested at pilot scale on 2 CPUs with "
                       "no network, and whether its falsifier is a concrete measurable result. "
                       "Score feasibility, falsifiability and evidence_fit harshly.",
}


def generation_prompt(topic, count=5, methodology=""):
    return (
        f"Propose {count} distinct research ideas for the topic below. Each must be a specific, "
        "testable hypothesis, not a theme.\n\n"
        "- `method`: how it would be tested, concretely enough to implement.\n"
        "- `falsifier`: the exact result that would DISPROVE it: a `statement`, the `metric` "
        "measured, and the numeric `threshold` at which the hypothesis is rejected. An idea "
        "without a measurable falsifier is useless here.\n"
        "- Prefer ideas testable at pilot scale (small models, small or synthetic data).\n"
        "- Do not pad: weak or duplicate ideas are worse than fewer ideas.\n\n"
        f"{methodology}\n\nTOPIC\n{topic}\n\nReturn JSON: {{\"ideas\": [{{id, title, hypothesis, method, falsifier}}]}}\n")


def review_prompt(persona, ideas):
    def falsifier_text(idea):
        f = idea.get("falsifier")
        if not isinstance(f, dict):
            return "NONE GIVEN"
        return f"{f.get('statement')} ({f.get('metric')}, threshold {f.get('threshold')})"

    listing = "\n\n".join(f"[{i.get('id')}] {i.get('title')}\nHypothesis: {i.get('hypothesis')}\n"
                          f"Method: {i.get('method')}\nFalsifier: {falsifier_text(i)}"
                          for i in ideas)
    return (f"You are an independent reviewer. {PERSONAS[persona]}\n\n"
            "Score EVERY idea below from 0 to 10 on novelty, importance, feasibility, "
            "falsifiability and evidence_fit. Do not hedge toward the middle.\n\n"
            f"IDEAS\n\n{listing}\n\nReturn JSON: {{\"reviews\": [{{idea_id, novelty, importance, "
            "feasibility, falsifiability, evidence_fit}]}\n")


def generate(topic_text, agent_factory, count=5, methodology=""):
    """Ideas from a topic, each scored by two separate reviewer calls."""
    agent = agent_factory()
    def candidate_check(payload):
        items = payload.get("ideas") if isinstance(payload, dict) else None
        if not isinstance(items, list) or len(items) < 2:
            return ["need at least two idea objects"]
        if any(not isinstance(item, dict) or not isinstance(item.get("id"), str)
               or not item["id"].strip() for item in items):
            return ["each idea needs a non-empty string ID"]
        ids = [item["id"] for item in items]
        return ["candidate idea IDs must be unique"] if len(ids) != len(set(ids)) else []

    ideas = agent.run(generation_prompt(topic_text, count, methodology), candidate_check,
                      schema_path=ASSETS / "ideas.schema.json")["payload"]["ideas"]
    ids = [i["id"] for i in ideas]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("generated candidate ideas need distinct non-empty string IDs")
    for persona in PERSONAS:
        def check(payload, persona=persona):
            rows = payload.get("reviews") if isinstance(payload, dict) else None
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                return ["reviews must be a list of objects"]
            reviewed = [r.get("idea_id") for r in rows]
            if (len(reviewed) != len(ids) or any(not isinstance(i, str) for i in reviewed)
                    or set(reviewed) != set(ids)):
                return ["each idea must have exactly one review; unknown and duplicate IDs are rejected"]
            return []
        reviews = agent_factory().run(review_prompt(persona, ideas), check,
                                      schema_path=ASSETS / "idea_reviews.schema.json")["payload"]["reviews"]
        by_id = {r["idea_id"]: r for r in reviews}
        for idea in ideas:
            row = by_id[idea["id"]]
            idea.setdefault("reviews", []).append(
                {"reviewer_id": persona, **{f: row[f] for f in SCORE_FIELDS}})
    return {"generated": True, "ideas": ideas}


def run(project, context=None, agent_factory=None):
    """Select from `_inputs/ideas.json`, or generate ideas from `_inputs/topic.md` first."""
    project = pathlib.Path(project)
    if (project / '_inputs' / 'v5_adoption.json').is_file():
        return select_v5(project)
    supplied = project / "_inputs" / "ideas.json"
    if supplied.is_file():
        return select(project, supplied)
    topic = project / "_inputs" / "topic.md"
    if not topic.is_file():
        raise ValueError("put ideas.json or topic.md in _inputs/")
    from factory.agents.loop import AgentLoop, LoopExhausted
    context = context or {}
    factory = agent_factory or (lambda: AgentLoop(
        context.get("idea_provider", "claude"), model=context.get("idea_model"), max_turns=3,
        workdir=project, budget_seconds=1800))
    try:
        from factory.integrations.ledger import enabled
        from factory.integrations.methodology import brief
        guidance = brief("idea") if enabled(context) else ""
        payload = generate(topic.read_text(encoding="utf-8"), factory,
                           int(context.get("idea_count", 5)), methodology=guidance)
    except LoopExhausted as exc:
        raise ValueError(f"idea generation failed: {exc}") from exc
    target = project / "1_idea" / "ideas.generated.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(target, payload)
    report = select(project, target)
    report["generated"] = True
    report["caveat"] = ("Ideas and their scores were produced by separate Claude calls, not "
                        "independent human or literature review. Check novelty yourself.")
    atomic_json(project / "1_idea" / "tournament.json", report)
    return report
