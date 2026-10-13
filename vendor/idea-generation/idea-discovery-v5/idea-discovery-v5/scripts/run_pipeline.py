"""
run_pipeline.py — Main Orchestrator (V5)
Runs all steps with quality gates, optional human checkpoint, and iterative attack/check/revise loops.

Modes:
  python scripts/run_pipeline.py              # Full run (auto mode)
  python scripts/run_pipeline.py --checkpoint  # Pause after gaps for human review
  python scripts/run_pipeline.py --resume      # Resume after human edits checkpoint
  python scripts/run_pipeline.py --skip-embeddings  # Skip heavy ML deps
  python scripts/run_pipeline.py --dashboard-only   # Regenerate dashboard from existing data
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_config, log, print_banner, save_json


def parse_args():
    parser = argparse.ArgumentParser(description="Idea Discovery Pipeline V5")
    parser.add_argument("--checkpoint", action="store_true",
                        help="Pause after gap detection for human review")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from human-edited checkpoint")
    parser.add_argument("--skip-embeddings", action="store_true",
                        help="Skip embedding/graph steps (no ML deps needed)")
    parser.add_argument("--dashboard-only", action="store_true",
                        help="Only regenerate dashboard from existing output")
    parser.add_argument("--no-quality", action="store_true",
                        help="Skip quality gate checks (faster)")
    parser.add_argument("--topic", type=str, default="",
                        help="Topic label for SESSION.md (e.g., 'LLM Reasoning')")
    parser.add_argument("--session-only", action="store_true",
                        help="Only regenerate SESSION.md from existing output")
    parser.add_argument("--falsification-only", action="store_true",
                        help="Run V5 falsification/MVE verification from existing attack-loop artifacts, then refresh downstream outputs")
    return parser.parse_args()


def main():
    args = parse_args()
    start = time.time()

    print_banner("IDEA DISCOVERY PIPELINE V5.0.0")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    config = load_config()
    cfg = config["pipeline"]
    output_dir = cfg["output_dir"]
    quality_enabled = config.get("quality_gates", {}).get("enabled", True) and not args.no_quality

    # ── Dashboard-only mode ──────────────────────────────────────────────
    if args.dashboard_only:
        print("Regenerating dashboard from existing data...\n")
        from step8_dashboard import generate_dashboard
        generate_dashboard(config)
        print(f"\nDashboard: {output_dir}/dashboard.html")
        return

    # ── Session-only mode ────────────────────────────────────────────────
    if args.session_only:
        print("Regenerating SESSION.md from existing data...\n")
        from step9_session import generate_session
        path = generate_session(config, topic=args.topic)
        print(f"\nSession file: {path}")
        print("Upload this single file to any LLM and start working!")
        return


    # ── Falsification-only mode ─────────────────────────────────────────
    if args.falsification_only:
        print("Running V5 falsification from existing adversarial survivors...\n")
        from step7c_falsification import run_falsification
        falsification_summary = run_falsification(config)
        from step7b_survivor_elo import run_survivor_elo
        elo_summary = run_survivor_elo(config)
        if config.get("scientific_governance", {}).get("methodology_blueprints", True):
            from step8_blueprints import run_blueprints
            run_blueprints(config)
        try:
            from ideation_memory import update_memory
            update_memory(config, falsification_summary, elo_summary)
        except Exception as e:
            log.warning(f"Ideation memory update skipped: {e}")
        from step7_report import compile_final_report
        compile_final_report(config)
        if config.get("dashboard", {}).get("enabled", True):
            from step8_dashboard import generate_dashboard
            generate_dashboard(config)
        from step9_session import generate_session
        generate_session(config, topic=args.topic)
        return

    # ── Resume mode ──────────────────────────────────────────────────────
    if args.resume:
        print("Resuming from human checkpoint...\n")
        from quality_gate import load_human_checkpoint
        checkpoint_result = load_human_checkpoint(config)
        if checkpoint_result["status"] == "waiting":
            print(f"\nEdit {output_dir}/CHECKPOINT_REVIEW.yaml")
            print("Set 'proceed: true' and run again with --resume")
            sys.exit(0)
        if checkpoint_result["status"] == "applied":
            print(f"Checkpoint applied: {checkpoint_result.get('removed',0)} gaps removed, "
                  f"{checkpoint_result.get('added',0)} added")
        # Jump to step 5
        _run_from_step5(config, args, quality_enabled)
        _finish(start, output_dir)
        return

    # ── Verify input ─────────────────────────────────────────────────────
    input_dir = Path(cfg["input_dir"])
    if not input_dir.exists():
        input_dir.mkdir(parents=True)
        print(f"Created '{input_dir}/' — add your papers there and run again.")
        sys.exit(0)

    papers = list(input_dir.glob("*.pdf")) + list(input_dir.glob("*.txt")) + list(input_dir.glob("*.md"))
    if not papers:
        print(f"No papers found in '{input_dir}/'. Add PDF, TXT, or MD files.")
        sys.exit(0)

    print(f"Found {len(papers)} papers in '{input_dir}/'")
    print(f"Quality gates: {'ON' if quality_enabled else 'OFF'}")
    print(f"Embeddings: {'SKIP' if args.skip_embeddings else 'ON'}")
    print(f"Checkpoint mode: {'ON' if args.checkpoint else 'OFF'}\n")

    # Track pipeline metadata
    pipeline_meta = {
        "started": datetime.now().isoformat(),
        "version": "5.0.0",
        "n_papers": len(papers),
        "flags": {
            "quality_gates": quality_enabled,
            "checkpoint": args.checkpoint,
            "skip_embeddings": args.skip_embeddings,
        },
        "step_timings": {},
    }

    # ── Step 1: Ingest ───────────────────────────────────────────────────
    t1 = time.time()
    from step1_ingest import run_ingestion
    corpus = run_ingestion(config)
    pipeline_meta["step_timings"]["step1_ingest"] = round(time.time() - t1, 1)

    # ── Step 1B: Programmatic source verification ───────────────────────
    if config.get("source_verification", {}).get("enabled", True):
        tv = time.time()
        try:
            from step1b_source_verify import run_source_verification
            run_source_verification(config)
        except Exception as e:
            log.warning(f"Source verification stage degraded gracefully: {e}")
        pipeline_meta["step_timings"]["step1b_source_verify"] = round(time.time() - tv, 1)

    # Quality gate: ingestion
    if quality_enabled and config.get("quality_gates", {}).get("check_ingestion", True):
        try:
            from quality_gate import critique_ingestion
            log.info("\n── Quality gate: ingestion ──")
            qr = critique_ingestion(config)
            quality = qr.get("overall_quality", "?")
            if quality == "NEEDS_REVIEW":
                log.warning("⚠️  Ingestion quality: NEEDS_REVIEW — check quality_ingestion.json")
        except Exception as e:
            log.warning(f"Ingestion quality check skipped: {e}")

    # ── Step 2: Cluster (hybrid) ─────────────────────────────────────────
    t2 = time.time()
    if args.skip_embeddings:
        # Use the old LLM-only clustering path
        log.info("Embeddings skipped — using LLM-only clustering")
        # Temporarily disable embeddings in config
        config["_skip_embeddings"] = True

    from step2_cluster import run_clustering
    space_map = run_clustering(config)
    pipeline_meta["step_timings"]["step2_cluster"] = round(time.time() - t2, 1)

    # Quality gate: clusters
    if quality_enabled and config.get("quality_gates", {}).get("check_clusters", True):
        try:
            from quality_gate import critique_clusters
            log.info("\n── Quality gate: clusters ──")
            qr = critique_clusters(config)
            quality = qr.get("cluster_quality", "?")
            if quality == "NEEDS_REVIEW":
                log.warning("⚠️  Cluster quality: NEEDS_REVIEW — check quality_clusters.json")
        except Exception as e:
            log.warning(f"Cluster quality check skipped: {e}")

    # ── Step 3: Conflicts ────────────────────────────────────────────────
    t3 = time.time()
    from step3_conflicts import run_conflict_detection
    conflicts = run_conflict_detection(config)
    pipeline_meta["step_timings"]["step3_conflicts"] = round(time.time() - t3, 1)

    # ── Step 4: Gaps ─────────────────────────────────────────────────────
    t4 = time.time()
    from step4_gaps import run_gap_detection
    gaps = run_gap_detection(config)
    pipeline_meta["step_timings"]["step4_gaps"] = round(time.time() - t4, 1)

    # ── Checkpoint mode ──────────────────────────────────────────────────
    if args.checkpoint:
        from quality_gate import save_human_checkpoint
        checkpoint_path = save_human_checkpoint(config)
        print(f"\n{'='*60}")
        print(f"  PIPELINE PAUSED — HUMAN CHECKPOINT")
        print(f"  ")
        print(f"  1. Open: {checkpoint_path}")
        print(f"  2. Review gaps, approve/reject/add your own")
        print(f"  3. Set 'proceed: true'")
        print(f"  4. Run: python scripts/run_pipeline.py --resume")
        print(f"{'='*60}\n")
        pipeline_meta["status"] = "paused_at_checkpoint"
        save_json(pipeline_meta, f"{output_dir}/pipeline_summary.json")
        sys.exit(0)

    # ── Steps 5-8 ────────────────────────────────────────────────────────
    _run_from_step5(config, args, quality_enabled, pipeline_meta)
    _finish(start, output_dir, pipeline_meta)


def _run_from_step5(config, args, quality_enabled, pipeline_meta=None):
    """Run V5 discovery, adversarial survival, empirical falsification, survivor ranking, and outputs."""
    if pipeline_meta is None:
        pipeline_meta = {"step_timings": {}}

    cfg = config["pipeline"]
    output_dir = cfg["output_dir"]

    # ── Step 4B: Literature grounding + problem selection ──────────────
    # Combines the supplied corpus with targeted academic search, builds
    # novelty/challenge-insight trees, and runs the Level 1–4 solution check.
    t4b = time.time()
    from step4b_discovery_grounding import run_discovery_grounding
    discovery = run_discovery_grounding(config)
    pipeline_meta["step_timings"]["step4b_discovery_grounding"] = round(time.time() - t4b, 1)

    # ── Step 5: Multi-persona idea evolution ───────────────────────────
    # Up to 3 fundamentally different directions; Innovator/Pragmatist/Critic
    # all write a revision every round. Only track champions move forward.
    t5 = time.time()
    from step5_evolution import run_idea_evolution
    ideas = run_idea_evolution(config)
    pipeline_meta["step_timings"]["step5_idea_evolution"] = round(time.time() - t5, 1)

    # Optional lightweight reviewer simulation remains diagnostic only.
    if ideas.get("ideas") and quality_enabled and config.get("quality_gates", {}).get("simulate_reviewer", True):
        try:
            from quality_gate import simulate_reviewer
            log.info("\n── Quality gate: pre-attack reviewer simulation ──")
            simulate_reviewer(config)
        except Exception as e:
            log.warning(f"Reviewer simulation skipped: {e}")

    # ── Step 6: Iterative adversarial survival loop ────────────────────
    # Phase 10 scorecard → Phase 11 novelty attack → Phase 12 novelty matrix
    # → Phase 13 Reviewer #1 attack → Phase 14 revise/kill → repeat.
    gov_cfg = config.get("scientific_governance", {})
    t6 = time.time()
    from step7_attack_loop import run_attack_loop
    attack_summary = run_attack_loop(config)
    pipeline_meta["step_timings"]["step6_attack_loop"] = round(time.time() - t6, 1)

    # ── Step 7: Falsification zone ─────────────────────────────────────
    # Hypothesis contract → Occam/counterexample attack → blind verifier
    # → MVE protocol → executed-evidence audit. No evidence = READY_FOR_MVE.
    tf = time.time()
    from step7c_falsification import run_falsification
    falsification_summary = run_falsification(config)
    pipeline_meta["step_timings"]["step7_falsification"] = round(time.time() - tf, 1)

    # ── Step 8: ELO tournament among FINAL GREENLIGHT survivors only ───
    t7 = time.time()
    from step7b_survivor_elo import run_survivor_elo
    elo_summary = run_survivor_elo(config)
    pipeline_meta["step_timings"]["step8_survivor_elo"] = round(time.time() - t7, 1)

    # ── Step 9: Methodology blueprints for FINAL GREENLIGHT ideas ──────
    if gov_cfg.get("methodology_blueprints", True):
        t8 = time.time()
        from step8_blueprints import run_blueprints
        run_blueprints(config)
        pipeline_meta["step_timings"]["step9_blueprints"] = round(time.time() - t8, 1)

    # ── Step 10: Update cross-run ideation memory ──────────────────────
    if config.get("ideation_memory", {}).get("enabled", True):
        tm = time.time()
        try:
            from ideation_memory import update_memory
            update_memory(config, falsification_summary, elo_summary)
        except Exception as e:
            log.warning(f"Ideation memory update skipped: {e}")
        pipeline_meta["step_timings"]["step9_ideation_memory"] = round(time.time() - tm, 1)

    # ── Step 11: Final report ───────────────────────────────────────────
    tr = time.time()
    from step7_report import compile_final_report
    compile_final_report(config)
    pipeline_meta["step_timings"]["step11_report"] = round(time.time() - tr, 1)

    # ── Step 12: Dashboard ─────────────────────────────────────────────
    if config.get("dashboard", {}).get("enabled", True):
        td = time.time()
        try:
            from step8_dashboard import generate_dashboard
            log.info("\n── Step 12: Interactive Dashboard ──")
            generate_dashboard(config)
        except Exception as e:
            log.warning(f"Dashboard generation skipped: {e}")
        pipeline_meta["step_timings"]["step12_dashboard"] = round(time.time() - td, 1)

    # ── Step 13: Portable Session File ─────────────────────────────────
    ts = time.time()
    try:
        from step9_session import generate_session
        log.info("\n── Step 13: Session File ──")
        topic = getattr(args, "topic", "") if args else ""
        generate_session(config, topic=topic)
    except Exception as e:
        log.warning(f"Session file generation skipped: {e}")
    pipeline_meta["step_timings"]["step13_session"] = round(time.time() - ts, 1)

def _finish(start, output_dir, pipeline_meta=None):
    """Print completion summary."""
    elapsed = time.time() - start
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    if pipeline_meta:
        pipeline_meta["status"] = "complete"
        pipeline_meta["completed"] = datetime.now().isoformat()
        pipeline_meta["total_seconds"] = round(elapsed, 1)
        save_json(pipeline_meta, f"{output_dir}/pipeline_summary.json")

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE in {mins}m {secs}s")
    print(f"  ")
    print(f"  Outputs:")
    print(f"    Report:    {output_dir}/FINAL_REPORT.md")
    dash = Path(f"{output_dir}/dashboard.html")
    if dash.exists():
        print(f"    Dashboard: {output_dir}/dashboard.html")
    session = Path(f"{output_dir}/SESSION.md")
    if session.exists():
        size_kb = session.stat().st_size // 1024
        print(f"    Session:   {output_dir}/SESSION.md ({size_kb}KB)")
        print(f"")
        print(f"  → Upload SESSION.md to any LLM and start working!")
    print(f"    All data:  {output_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
