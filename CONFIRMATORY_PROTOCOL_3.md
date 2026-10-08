# Confirmatory protocol 3: robust comparison on new instances

**Status: proposed.** This protocol becomes fixed only when it is publicly
timestamped together with `FROZEN_MANIFEST_3.json` (a public repository commit
and a Zenodo release), before any robust plan is computed for an instance of
this study.

## Why this study exists

The manuscript compares the screened procedures with a budgeted-robust VRPTW
optimizer (Bertsimas and Sim; Agra et al.) on the development instances with
up to 100 customers (Sections 10 and 11.11). That comparison was exploratory:
its grid was fixed before the runs, but no hypothesis was. Its main findings
were that the robust model with reachability relief, passed through the
screening layer ("screened robust with relief"), was more reliable than the
OR-Tools and HGS capped procedures, used more vehicles than the HGS capped
procedure, and was shorter than the most protective relieved setting while
slightly less reliable. This study tests those findings on instances that no
design decision of the robust comparison has seen.

## What has and has not been seen (disclosed)

- No robust plan has been computed for any instance of this study.
- The comparators are stored results of confirmatory studies 1 and 2, which
  are published: the OR-Tools capped procedure on both sets, and the HGS capped
  procedure with conservative fallback on the set of study 2. Their validated
  service on these instances is therefore known. The hypotheses below were
  chosen from the development comparison and are the contrasts reported there;
  no comparator was chosen or dropped on the basis of the confirmatory results.
- Exploratory robust runs with 200 customers on the development instances, and
  any other exploratory analysis, may run in parallel and are reported as
  exploratory. They do not touch the instances of this study.

## Design

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

## Quantities

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

## Hypotheses

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

## Decision rules

- Paired bootstrap over instances: 20,000 resamples, seed 20260930, percentile
  intervals.
- R1 and R2 are Bonferroni-adjusted: each is **confirmed** only if its
  two-sided 97.5% interval lies entirely above zero.
- R3 and R4 use 95% intervals; R3 is confirmed if its interval lies above zero,
  R4 if its interval lies below zero. They are secondary and cannot rescue an
  unconfirmed primary hypothesis.
- Decisions use unrounded interval limits. An interval containing zero is "not
  confirmed", never evidence of no effect.
- Every hypothesis is reported whatever its outcome. If R1 or R2 is not
  confirmed, the abstract and conclusion must say so.
- "Confirmed" means only that a hypothesis met its decision criterion in this
  prespecified synthetic setting. The instances share the generator and
  disturbance model of the development study.

## Failure policy

A setting without a robust feasible plan has status `no_plan` and scores 0.
Any other exception is a software error: it is written to a
`software_error_<seed>.json` file, never scored, and blocks the analysis;
fixing it changes frozen code and must be reported as a labelled deviation.

## Analysis safeguards

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

## Procedure

Run from the package root (`PYTHONPATH=code OPENBLAS_NUM_THREADS=1`).

```bash
# 0. Freeze: write the manifest; commit this protocol and the manifest
#    together, publicly; publish a release so Zenodo timestamps it.
python code/freeze_manifest_robust.py

# 1. Robust plans (the search is deterministic, so the number of workers does
#    not change the plans).
python code/study_robust.py --sizes 100 50 20 --capped --seed-shift 60000 \
  --output results/confirm/robust_capped --workers 2
python code/study_robust.py --sizes 100 50 20 --capped --seed-shift 80000 \
  --output results/confirm2/robust_capped --workers 2

# 2. The prespecified analysis, and nothing else.
python code/confirm_analysis_robust.py confirmatory \
  --output results/confirm_robust_analysis_output.json
```

Record the hardware and elapsed times. Any deviation from this document must
be reported in the manuscript as a labelled deviation, with its reason.
