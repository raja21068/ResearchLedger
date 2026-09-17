# A Minimal Example Paper

## Abstract

We report a baseline classifier's accuracy on a held-out split, verified across two independent
seeds.

## 1. Introduction

This is a shipped example, not a real paper — see [`../../project.md`](../../project.md).

## 2. Related Work

(omitted — example workspace)

## 3. Method

A standard baseline classifier trained with `configs/base.yaml`.

## 4. Experiments

We trained the baseline with two different random seeds and report accuracy on the held-out
split for each.

## 5. Results

Our baseline classifier reaches over 90% accuracy on the held-out split, verified across two
independent seeds (91.4% and 90.9%).
<!-- rl:claim=C001 -->

## 6. Discussion

Both seeds clear the accuracy threshold with a tight spread, which is what actually justifies
treating this as verified rather than a single lucky run — see `research/evidence/E001.md`.

## 7. Conclusion

The baseline is a defensible reference point going forward — see `research/decisions/D001.md`.
