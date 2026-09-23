from __future__ import annotations
import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(*parts):
    cmd=[sys.executable,*map(str,parts)]
    print('+',' '.join(cmd),flush=True)
    subprocess.run(cmd,cwd=ROOT.parent,check=True)

def main():
    run(ROOT/'run_semantic_replay.py')
    run(ROOT/'analysis'/'expanded_semantic_replay.py')
    run(ROOT/'analysis'/'transaction_fault_injection.py')
    run(ROOT/'trajectory_runner.py')
    run(ROOT/'analysis'/'bootstrap_repository_clustered.py')
    run(ROOT/'annotation_tool.py','generate')
    print('validation-study regeneration complete')
if __name__=='__main__': main()
