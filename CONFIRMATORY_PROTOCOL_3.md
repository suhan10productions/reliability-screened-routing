# Confirmatory protocol 3: robust comparison and fallback rule

**Status: proposed.** This protocol becomes fixed only when it is publicly
timestamped together with `FROZEN_MANIFEST_3.json` (a public repository commit
and a Zenodo release), before any robust plan is computed for an instance of
part A and before any instance of part B is solved.

The protocol has two independent parts. Part A tests the robust comparison on
the existing confirmatory instances. Part B tests a new fallback rule on 53 new
instances. Each part has its own hypotheses and its own multiplicity
adjustment.

# Part A: robust comparison on the confirmatory instances

## Why part A exists

The manuscript compares the screened procedures with a budgeted-robust VRPTW
optimizer (Bertsimas and Sim; Agra et al.) on the development instances with
up to 100 customers (Sections 10 and 11.11). That comparison was exploratory:
its grid was fixed before the runs, but no hypothesis was. Its main findings
were that the robust model with reachability relief, passed through the
screening layer ("screened robust with relief"), was more reliable than the
OR-Tools and HGS capped procedures, used more vehicles than the HGS capped
procedure, and was shorter than the most protective relieved setting while
slightly less reliable. Part A tests those findings on instances that no
design decision of the robust comparison has seen.

## What has and has not been seen (disclosed)

- No robust plan has been computed for any instance of part A.
- The comparators are stored results of confirmatory studies 1 and 2, which
  are published: the OR-Tools capped procedure on both sets, and the HGS capped
  procedure with conservative fallback on the set of study 2. Their validated
  service on these instances is therefore known. The hypotheses below were
  chosen from the development comparison and are the contrasts reported there;
  no comparator was chosen or dropped on the basis of the confirmatory results.
- Exploratory robust runs with 200 customers on the development instances, and
  any other exploratory analysis, may run before part A and are reported as
  exploratory. They do not touch the instances of this protocol.

## Design (part A)

| Item | Value |
|---|---|
| Instances | the confirmatory instances with 20, 50 and 100 customers: study 1 seeds 67200-67219, 67500-67514, 68000-68009; study 2 seeds 87200-87219, 87500-87514, 88000-88009 (90 instances) |
| Instance generator and fleet | `make_synthetic_instance`, fleets 6 / 14 / 26 at n = 20 / 50 / 100, unchanged |
| Robust model | `CappedRobustModel` (budgeted uncertainty with reachability relief), `robust_generator.py` |
| Grid | Gamma in {1, 2, 3, 5, box} x theta in {0.2, 0.4, 0.6}: 15 relieved settings |
| Search | large neighbourhood search, 6000 iterations at n = 20 and 50, 3000 at n = 100, seed = instance seed (deterministic) |
| Screening bank | 1000 scenarios, seed 100000 + instance seed (the study's screening bank) |
| Validation bank | 5000 scenarios, seed 400000 + instance seed (the bank on which the comparators were validated) |
| Disturbance model | as in the manuscript (sigma 0.20, rho 0.5, unchanged speed profile) |

Instances with 200 customers are excluded, as in the development comparison,
because the robust search is slow at that size.

## Quantities (part A)

The unit is the instance. Service is the validated kappa = 0.95 service-event
probability on the validation bank; a configuration without a plan scores 0.

- `screened_relief`: among the 15 relieved settings with a plan, the shortest
  plan whose one-sided 95% Wilson lower bound on the screening bank reaches
  0.95; if none does, the plan with the highest screening success (ties by
  shorter distance). This is `analyse_robust.screened_robust`, unchanged.
- `relief_box_0.6`: the relieved setting with box uncertainty and theta = 0.6.
- `ort_capped`: the stored OR-Tools capped procedure (studies 1 and 2).
- `hgs_capped_cons`: the stored HGS capped procedure with conservative
  fallback (study 2 only).
- Vehicles: the number of vehicles used by a plan. Distance: planned distance.

## Hypotheses (part A)

- **R1 (primary).** Screened robust with relief exceeds the OR-Tools capped
  procedure in service: mean paired difference
  `screened_relief - ort_capped` > 0 over all 90 instances.
- **R2 (primary).** Screened robust with relief exceeds the HGS capped
  procedure with conservative fallback in service: mean paired difference
  `screened_relief - hgs_capped_cons` > 0 over the 45 instances of study 2.
- **R3 (secondary).** Screened robust with relief uses more vehicles than the
  HGS capped procedure: mean paired difference in vehicles > 0, over the
  instances of study 2 on which both have a plan.
- **R4 (secondary).** Screened robust with relief is shorter than the most
  protective relieved setting: mean of 100 (distance of `screened_relief` /
  distance of `relief_box_0.6` - 1) < 0, over the instances on which both have
  a plan.

Descriptive only: the service difference `relief_box_0.6 - screened_relief`,
the number of instances on which screening admitted a robust plan, pooled
service of every setting, and results by size.

## Decision rules (both parts)

- Paired bootstrap over instances: 20,000 resamples, seed 20260930, percentile
  intervals.
- Within each part, the two primary hypotheses (R1 and R2; F1 and F2) are
  Bonferroni-adjusted: each is **confirmed** only if its two-sided 97.5%
  interval lies entirely above zero.
- R3 and R4 use 95% intervals; R3 is confirmed if its interval lies above zero,
  R4 if its interval lies below zero. They are secondary and cannot rescue an
  unconfirmed primary hypothesis.
- Decisions use unrounded interval limits. An interval containing zero is "not
  confirmed", never evidence of no effect.
- F3 and F4 are estimates with 95% intervals, without a decision.
- Every hypothesis is reported whatever its outcome. If a primary hypothesis is
  not confirmed, the abstract and conclusion must say so.
- "Confirmed" means only that a hypothesis met its decision criterion in this
  prespecified synthetic setting. The instances share the generator and
  disturbance model of the development study.

## Failure policy (both parts)

In part A, a setting without a robust feasible plan has status `no_plan` and scores 0.
Any other exception is a software error: it is written to a
`software_error_<seed>.json` file, never scored, and blocks the analysis;
fixing it changes frozen code and must be reported as a labelled deviation.
In part B, the failure policy of protocol 2 applies unchanged.

## Analysis safeguards (part A)

`code/confirm_analysis_robust.py confirmatory` computes nothing until it has:

- checked every file in its manifest list against `FROZEN_MANIFEST_3.json`;
- checked, for both studies, the exact seed set and sizes, one record per seed
  named for its seed, no other files in the output directory, the schema, fleet
  size, iterations, search seed, screening and validation seeds, scenario
  counts, the 15-setting relieved grid, statuses agreeing with plans, screening
  and validation, and every plan visiting each customer exactly once;
- checked that the stored OR-Tools (and, for study 2, HGS) record exists for
  every instance, with the same fleet size.

Only this mode prints "CONFIRMED" or "NOT CONFIRMED". The `descriptive` mode
runs the same code on the development instances; it was run before the freeze
and reproduces the exploratory results of Section 11.11.

# Part B: best-screened fallback on new instances

## Why part B exists

When screening admits no candidate, the OR-Tools procedures return the
uncontracted slack-aware plan and the HGS procedure returns the
conservative-speed plan. These fallbacks are the main reason the procedures
pool below the 95% target. A post hoc analysis of the stored records
(`code/fallback_policy.py`) found that a rule using the screening evidence
already computed did much better on the development instances and on both
confirmatory studies: return the family's candidate with the highest
screening success. Because that rule was chosen after those results were
seen, part B tests it on instances that no decision has seen.

## What has and has not been seen (disclosed)

- No instance with seeds + 120000 has been generated or solved.
- The rule was chosen after the development and both confirmatory studies,
  whose stored records it was evaluated on. That analysis is exploratory.

## Design (part B)

| Item | Value |
|---|---|
| Instance seeds | development seeds + 120000: 127200-127219, 127500-127514, 128000-128009, 129000-129007 |
| Instances | 20 / 15 / 10 / 8 at n = 20 / 50 / 100 / 200 (53 in total) |
| OR-Tools half | the frozen pipeline, unchanged: `study_v6.py` then `study_v7.py` |
| HGS half | `study_hgs.py` with `hgs_generator.py`, 10,000 iterations, seed = instance seed |
| Scenario banks | screening 1000 at 100000 + seed; validation 5000 at 400000 + seed |
| Everything else | as in protocol 2 and manuscript Table 2 |

The seeds and every scenario-bank seed derived from them (100000, 200000,
400000 and 500000 + seed) overlap no earlier study, pilot or abandoned set.
The runs use the pinned versions in `requirements.txt` on a two-core Linux
machine. OR-Tools solves stop at a wall-clock limit, so the hardware is
recorded and the steps run one at a time with the machine otherwise idle.

## Quantities (part B)

- `ort_capped`: the OR-Tools capped procedure as specified in study 1
  (slack-aware fallback).
- `ort_capped_best`: the same selections; where screening admits no candidate,
  the best-screened fallback.
- `hgs_capped_cons`: the HGS capped procedure with conservative fallback, as in
  protocol 2.
- `hgs_capped_best`: the same selections; where screening admits no candidate,
  the best-screened fallback.
- Best-screened fallback: the candidate of the procedure's own capped family
  with the highest success on the screening bank (ties: lower normalized score
  with the record's scaling ranges, then the smaller buffer). If no candidate
  has a plan, the procedure's own stored fallback is kept. The rule uses no
  validation outcome; the chosen plan is validated once on the fresh bank.

## Hypotheses (part B)

- **F1 (primary).** The best-screened fallback improves the OR-Tools capped
  procedure: mean paired difference `ort_capped_best - ort_capped` > 0 over all
  53 instances.
- **F2 (primary).** The best-screened fallback improves the HGS capped
  procedure: mean paired difference `hgs_capped_best - hgs_capped_cons` > 0
  over all 53 instances.
- **F3 (estimate).** Pooled service of `ort_capped_best`, with a 95% interval.
- **F4 (estimate).** Pooled service of `hgs_capped_best`, with a 95% interval.

## Analysis safeguards (part B)

`code/confirm_analysis_fallback.py confirmatory` checks `FROZEN_MANIFEST_3.json`
and then validates both halves with the frozen validators of protocol 2
(`confirm_analysis.py` and `confirm_analysis_hgs.py`, unchanged), pointed at the
seed set + 120000 and at `FROZEN_MANIFEST_2.json`. Only then does it compute
F1-F4. Its `descriptive` mode computes the same quantities on the development
and second confirmatory records; it was run before the freeze and reproduces
the post hoc analysis.

# Procedure (both parts)

Run from the package root (`PYTHONPATH=code OPENBLAS_NUM_THREADS=1`).

```bash
# 0. Freeze: write the manifest; commit this protocol and the manifest
#    together, publicly; publish a release so Zenodo timestamps it.
python code/freeze_manifest_robust.py

# Part B first: it uses wall-clock-limited OR-Tools solves, so it runs on an
# otherwise idle machine.
# B1. OR-Tools half, stage 1 (the sizes may run two at a time).
mkdir -p results/confirm3
for n in 20 50 100 200; do
  python code/study_v6.py --sizes $n --seed-shift 120000 \
    --output results/confirm3/study_v6_n$n.json
done
# B2. OR-Tools half, stage 2.
python code/study_v7.py \
  --inputs results/confirm3/study_v6_n20.json results/confirm3/study_v6_n50.json \
           results/confirm3/study_v6_n100.json results/confirm3/study_v6_n200.json \
  --output results/confirm3/v7 --workers 2 --seconds 5
# B3. HGS half.
python code/study_hgs.py --seed-shift 120000 --output results/confirm3/hgs --workers 2
# B4. The prespecified analysis of part B, and nothing else.
python code/confirm_analysis_fallback.py confirmatory \
  --output results/confirm3_fallback_analysis_output.json

# A1. Robust plans (the search is deterministic, so the number of workers does
#     not change the plans).
python code/study_robust.py --sizes 100 50 20 --capped --seed-shift 60000 \
  --output results/confirm/robust_capped --workers 2
python code/study_robust.py --sizes 100 50 20 --capped --seed-shift 80000 \
  --output results/confirm2/robust_capped --workers 2

# A2. The prespecified analysis of part A, and nothing else.
python code/confirm_analysis_robust.py confirmatory \
  --output results/confirm_robust_analysis_output.json
```

Record the hardware and elapsed times. Any deviation from this document must
be reported in the manuscript as a labelled deviation, with its reason.
