# Confirmatory protocol

**Status: proposed.** This protocol becomes fixed only when it is publicly
timestamped together with `FROZEN_MANIFEST.json` (a public repository commit
or an OSF registration), before any confirmatory instance is solved. Until
then it must be described as a proposed protocol, not a frozen one.

## Pilot data (disclosed)

While preparing this protocol, one instance was solved as a pipeline smoke
test: seed 57200 (the first instance of an earlier candidate seed set, shift
50000), with one-second solves and reduced scenario counts. Its outputs were
seen. That earlier candidate set is therefore abandoned in full, and seed
57200 is classified as pilot data, excluded from every confirmatory analysis.

The confirmatory set below uses shift 60000. No instance in it, and no
scenario bank derived from it, has been generated or solved. Its screening,
validation and sweep seeds do not overlap the development study or the pilot.

## Why this study exists

Every result in the manuscript comes from the same 53 synthetic instances
(seeds 7200-9007). Those instances motivated the later design choices: capped
contraction, the conservative-speed comparator and the clock-aware
approximation were all introduced after earlier results on them were seen.
Fresh scenario banks do not remove that reuse, so the manuscript's findings are
exploratory. This study tests them on instances that no design decision has
seen. It tests repeatability within the same instance generator; it does not
establish performance on other routing environments.

## Design

Everything matches the development study except the instance seeds.

| Item | Value |
|---|---|
| Instance seeds | development seeds + 60000: 67200-67219, 67500-67514, 68000-68009, 69000-69007 |
| Instances | 20 / 15 / 10 / 8 at n = 20 / 50 / 100 / 200 (53 in total) |
| Generator | `make_synthetic_instance`, unchanged |
| Parameters | all values in manuscript Table 2, unchanged |
| Candidate budget | 5 s per solve; at most 3 attempts; first feasible result kept |
| Anchor budget | 2 s per anchor solve |
| Buffer grid | beta in {0, 5, ..., 60} |
| Scenarios | screening 1000; stage-1 validation 5000; fresh validation 5000; sweep 1000 per cell |
| Scenario seeds | 100000 / 200000 / 400000 / 500000 + instance seed, as in development |
| Bootstrap | paired, 20,000 resamples, analysis seed 20260930 |

## Hypotheses

P, C and K denote the original procedure, conservative-speed distance and the
capped procedure. The unit is the instance; the outcome is validated kappa =
0.95 service-event probability on the fresh bank.

- **H1 (primary).** On instances where C returns a plan, P exceeds C: mean
  paired difference P - C > 0, pooled over sizes.
- **H2 (primary).** On all instances, K exceeds P: mean paired difference
  K - P > 0, pooled over sizes.
- **H3 (secondary).** K is admitted on more instances than P: discordant
  counts with an exact two-sided binomial (McNemar) test.
- **H4 (secondary).** On exactly H1's subset, (P - C) at sigma = 0.30,
  rho = 0 exceeds (P - C) at sigma = 0.10, rho = 0. A configuration without a
  plan scores 0 in every sweep cell, under the failure policy below.

## Decision rules

- H1 and H2 are Bonferroni-adjusted. Each is **confirmed** only if its
  two-sided 97.5% paired bootstrap interval lies entirely above zero.
- H3 uses the exact test at 0.05; H4 a 95% interval. Both are secondary and
  cannot rescue an unconfirmed primary hypothesis.
- Size-specific results are descriptive only.
- An interval containing zero is reported as "not confirmed", never as
  evidence of no effect.
- Every decision is computed from unrounded interval limits and p-values;
  rounding is applied only to displayed values.
- Every hypothesis is reported whatever its outcome. If H1 or H2 is not
  confirmed, the abstract and conclusion must say so.

## Failure policy (fixed in advance)

Outcomes are recorded per configuration, and a failure of one configuration
never removes another configuration's result.

- **No plan.** A solver that returns no plan after its permitted attempts is a
  routing outcome. That configuration is recorded as `no_plan` with its reason.
- **Not attempted.** A configuration whose prerequisite has no plan is recorded
  as `not_attempted`, naming the prerequisite. The prerequisites are: the
  anchor solves for the slack-aware objective, the screened procedure and the
  capped procedure; the slack-aware plan for fleet-matched distance; and the
  nominal plan for the clock-aware approximation. The procedures fall back as
  described in the manuscript; a procedure with neither a selection nor a
  fallback base has no plan.
- **Scoring.** In the analysis, a configuration with no plan, for either
  reason, scores service probability 0 on that instance, in validation and in
  every sweep cell. A failure therefore counts against the configuration that
  failed and leaves every other configuration's outcome unchanged.
- **Subsets.** H1 and H4 use instances where C returns a plan, as in the
  development study. The number of instances outside that subset is reported.
- **Software errors are not routing outcomes.** Any exception other than a
  solver returning no plan is a software error. The drivers record it with
  its traceback and continue with other instances, but it is never scored.
  The confirmatory analysis refuses to run while any software error exists.
  Fixing one changes the frozen code, so the fix, the re-freeze and the rerun
  of affected instances must be reported as a labelled deviation.

## Analysis safeguards

`code/confirm_analysis.py confirmatory` computes nothing until it has checked:

- the protocol and all code match `FROZEN_MANIFEST.json`;
- stage 1 contains exactly the complete prescribed seed set, each seed once and
  at its prescribed size, with no size outside the design and no software
  errors; each stage-2 record has the same size as its stage-1 record;
- every stage-1 run parameter, and the stage-1 screening and validation seed
  derivations;
- every stage-1 configuration status agrees with whether its plan exists;
- stage 2 contains exactly one record per stage-1 instance, each named for its
  own seed, with no software-error or other unexpected files;
- each stage-2 record derives from its stage-1 record (SHA-256);
- the stage-2 candidate budget and screening, validation and sweep seeds;
- every configuration and its status are present and agree;
- every existing plan was validated on 5000 scenarios and swept over exactly
  the nine prescribed cells, each with 1000 scenarios.

Any violation aborts. Only this mode prints "CONFIRMED" or "NOT CONFIRMED".
The `descriptive` mode labels its output as descriptive and never prints a
verdict; it is the only mode that accepts the development records.
`code/check_confirmatory_safeguards.py` demonstrates each check on synthetic
fixtures, using the running interpreter and environment.

## Procedure

```bash
# 0. Freeze: write the manifest, then commit this protocol and the manifest
#    together, publicly. Record the commit hash or registration link.
PYTHONPATH=code python code/freeze_manifest.py

# 1. Candidates and screening on the fresh instances.
for n in 20 50 100 200; do
  PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python code/study_v6.py --sizes $n --seed-shift 60000 \
      --output results/confirm/study_v6_n$n.json
done

# 2. Added configurations and fresh validation.
PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python code/study_v7.py \
    --inputs results/confirm/study_v6_n20.json results/confirm/study_v6_n50.json \
             results/confirm/study_v6_n100.json results/confirm/study_v6_n200.json \
    --output results/confirm/v7 --workers 6 --seconds 5

# 3. The prespecified analysis, and nothing else.
PYTHONPATH=code python code/confirm_analysis.py confirmatory \
  --stage1 results/confirm/study_v6_n20.json results/confirm/study_v6_n50.json \
           results/confirm/study_v6_n100.json results/confirm/study_v6_n200.json \
  --stage2 results/confirm/v7 --manifest FROZEN_MANIFEST.json
```

Record the hardware and elapsed time. Any deviation from this document must be
reported in the manuscript as a labelled deviation, with its reason.
