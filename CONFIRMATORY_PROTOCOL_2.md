# Confirmatory protocol 2: stronger generator and fallback rule

**Status: proposed.** This protocol becomes fixed only when it is publicly
timestamped together with `FROZEN_MANIFEST_2.json` (a public repository commit
and a Zenodo release), before any instance of this study is solved.

## Abandoned seed set (disclosed)

An earlier version of this protocol prescribed seeds + 70000. The OR-Tools half
(stages 1 and 2) was run on those seeds before the protocol was publicly
timestamped, and the console output, which lists which instances screening
admitted, was seen. Those seeds are therefore abandoned in full. Their records
are kept in `results/abandoned_70000/` for transparency and are excluded from
every analysis; no hypothesis was computed on them. This study uses seeds
+ 80000 instead, with no other change. Before any instance of this study is
solved, `code/check_freeze_2.py` must pass.

## Why this study exists

Confirmatory study 1 (`CONFIRMATORY_PROTOCOL.md`) confirmed four hypotheses
with an OR-Tools candidate generator. Reviewers raised two questions it cannot
answer:

1. **Generator.** OR-Tools is below the state of the art. Does the benefit of
   statistical screening survive when candidates come from a strong generator
   (PyVRP's hybrid genetic search, HGS)?
2. **Fallback.** When screening admits no plan, the procedure returns the
   uncontracted slack-aware plan. A conservative-speed fallback looked better,
   but that comparison was chosen after the results of study 1 were seen.

Both questions are tested here on instances that no design decision has seen.
The HGS generator and this protocol were developed on the 53 development
instances; those runs are exploratory and are reported as such.

## Design

| Item | Value |
|---|---|
| Instance seeds | development seeds + 80000: 87200-87219, 87500-87514, 88000-88009, 89000-89007 |
| Instances | 20 / 15 / 10 / 8 at n = 20 / 50 / 100 / 200 (53 in total) |
| Generator of instances | `make_synthetic_instance`, unchanged |
| OR-Tools half | the frozen pipeline, unchanged: `study_v6.py` then `study_v7.py`, as in study 1 |
| HGS half | `study_hgs.py` with `hgs_generator.py` |
| HGS budget | 10,000 iterations per solve, seed = instance seed |
| Scaling ranges | from the unchanged OR-Tools anchor solves (2 s each), used by both halves |
| Scenario banks | screening 1000 at 100000 + seed; validation 5000 at 400000 + seed (both halves) |
| Everything else | as in study 1 and manuscript Table 2 |

No seed of this study, and no scenario bank derived from it, overlaps the
development study (7200-9007), the pilot (57200), study 1 (67200-69007) or the
abandoned set (77200-79007) described below.

The HGS generator solves the same planning model as the OR-Tools generator
(static matrix at the planning speed, hard and possibly contracted windows,
capacity, shift, fleet). Its weighted objective contains the distance, driver
duration and fleet terms with the same coefficients; PyVRP cannot express the
slack-deficit term, so that term is omitted from generation and kept in
candidate selection. Each vehicle departs at the latest feasible time, as with
OR-Tools. HGS solves stop after a fixed number of iterations, so they are
deterministic for given inputs; the scaling ranges they use come from
time-limited OR-Tools anchor solves, so the HGS half is deterministic given
those ranges, not across machines in every case.

## Quantities

The unit is the instance. Each quantity is validated kappa = 0.95
service-event probability on the fresh bank. A configuration without a plan
scores 0.

- `hgs_conservative`: HGS distance plan at conservative speed (33.3 km/h).
- `hgs_capped_cons`: HGS capped screened procedure; if screening admits no
  plan, it returns `hgs_conservative` (or the HGS beta-0 plan if that is absent).
- `ort_capped`: the OR-Tools capped procedure as specified in study 1, with its
  slack-aware fallback.
- `ort_capped_cons`: the same OR-Tools selections; if screening admits no plan,
  the OR-Tools conservative-speed plan is returned (or the slack-aware plan if
  the conservative plan is absent).
- `ort_procedure`, `ort_procedure_cons`: the same two rules for the uncapped
  OR-Tools procedure.

The fallback variants change no screening decision and use no validation
outcome; they only change which plan is returned when screening admits nothing.

## Hypotheses

- **G1 (primary).** On instances where `hgs_conservative` has a plan, the HGS
  capped procedure with conservative fallback exceeds HGS conservative-speed
  planning: mean paired difference `hgs_capped_cons - hgs_conservative` > 0.
- **G2 (primary).** On all instances, the conservative fallback improves the
  OR-Tools capped procedure: mean paired difference
  `ort_capped_cons - ort_capped` > 0.
- **G3 (secondary).** The same for the uncapped OR-Tools procedure:
  `ort_procedure_cons - ort_procedure` > 0.
- **G4 (secondary, estimate only).** The difference
  `hgs_capped_cons - ort_capped_cons` with a 95% interval, reported without a
  directional decision.

## Decision rules

- G1 and G2 are Bonferroni-adjusted: each is **confirmed** only if its
  two-sided 97.5% paired bootstrap interval (20,000 resamples, seed 20260930)
  lies entirely above zero.
- G3 uses a 95% interval and is secondary; it cannot rescue an unconfirmed
  primary hypothesis. G4 is an estimate.
- Decisions use unrounded interval limits.
- An interval containing zero is "not confirmed", never evidence of no effect.
- Every hypothesis is reported whatever its outcome. If G1 or G2 is not
  confirmed, the abstract and conclusion must say so.
- Results by size and the HGS configurations not named above are descriptive.

## Failure policy

As in study 1. Outcomes are recorded per configuration as `ok`, `no_plan` or
`not_attempted`. A missing plan scores 0. Any other exception is a software
error: it is recorded with its traceback, never scored, and blocks the
analysis; fixing it changes frozen code and must be reported as a labelled
deviation.

## Analysis safeguards

`code/confirm_analysis_hgs.py confirmatory` computes nothing until it has:

- checked every file in its manifest list against `FROZEN_MANIFEST_2.json`;
- validated the OR-Tools half with the frozen validator of study 1, pointed at
  this study's seed set (exact seeds and sizes, run parameters, scenario counts
  and seeds, provenance hashes, statuses, sweep cells, no software errors);
- validated the HGS half: exact seed set and sizes, one record per seed named
  for its seed, no unexpected or software-error files, run parameters
  (iterations, scenario counts, beta grid, anchor budget), scenario and HGS
  seeds, pinned versions of PyVRP, OR-Tools and NumPy, statuses agreeing with
  plans, 5000 validation scenarios, and every plan visiting each customer once;
- checked that both halves cover the same instances.

Only this mode prints "CONFIRMED" or "NOT CONFIRMED".
`code/check_hgs_safeguards.py` demonstrates each check.

## Procedure

Run from the package root with the pinned environment
(`PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`).

```bash
# 0. Freeze: write the manifest; commit this protocol and the manifest
#    together, publicly; publish a release so Zenodo timestamps it.
python code/freeze_manifest_hgs.py

# 1. OR-Tools half, stage 1 (the four sizes may run in parallel).
mkdir -p results/confirm2
for n in 20 50 100 200; do
  python code/study_v6.py --sizes $n --seed-shift 80000 \
    --output results/confirm2/study_v6_n$n.json
done

# 2. OR-Tools half, stage 2.
python code/study_v7.py \
  --inputs results/confirm2/study_v6_n20.json results/confirm2/study_v6_n50.json \
           results/confirm2/study_v6_n100.json results/confirm2/study_v6_n200.json \
  --output results/confirm2/v7 --workers 6 --seconds 5

# 3. HGS half.
python code/study_hgs.py --seed-shift 80000 --output results/confirm2/hgs --workers 6

# 4. The prespecified analysis, and nothing else.
python code/confirm_analysis_hgs.py confirmatory \
  --stage1 results/confirm2/study_v6_n20.json results/confirm2/study_v6_n50.json \
           results/confirm2/study_v6_n100.json results/confirm2/study_v6_n200.json \
  --stage2 results/confirm2/v7 --hgs results/confirm2/hgs --manifest FROZEN_MANIFEST_2.json
```

Record the hardware and elapsed times. Run steps 1-3 one at a time, with the
machine otherwise idle. Any deviation from this document must be reported in
the manuscript as a labelled deviation, with its reason.
