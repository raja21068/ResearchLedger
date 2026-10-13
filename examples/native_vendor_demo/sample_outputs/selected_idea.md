# Multi-level leakage stress test for brain MRI segmentation

## Hypothesis

Compared with random-slice splitting, patient- and acquisition-site-disjoint evaluation yields a mean Dice decrease exceeding 0.03 on sufficiently heterogeneous, legitimately obtained datasets; a preregistered study would test this prediction.

## Falsifier

Reject the preregistered overoptimism hypothesis if the paired mean Dice gap is at most 0.03.

Metric: `paired_mean_dice_gap_random_slice_minus_site_holdout`; disproved at threshold 0.03.

## Method

On licensed multi-site segmentation data, compare random-slice, patient-disjoint and site-holdout splits with the same architecture and fixed tuning budget. Report bootstrapped site-cluster intervals and repeat seeds.

## Selection

Selected from 3 falsifiable ideas (0 rejected as unfalsifiable) with an aggregate reviewer score of 7.9 on a 0-10 scale.

| criterion | mean score |
|---|---:|
| evidence_fit | 7.5 |
| falsifiability | 9.0 |
| feasibility | 7.5 |
| importance | 9.0 |
| novelty | 6.5 |

## Ideas not selected

- MRI-02: Calibrated abstention for domain-shift segmentation (7.1)
- MRI-03: Worst-site threshold tuning under imaging shift (6.2)
