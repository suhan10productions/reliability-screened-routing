# Response to the matched-comparison and generator review

All added experiments were run under the fixed protocol before the final
claims were written. The 53 instances and original candidate records are
retained; every fixed output receives a new 5,000-scenario validation bank.
This is an exploratory revision on the same synthetic instance set, not an
external replication. Small movements in old-plan probabilities relative to
the previous paper are caused by new validation draws. The vectorized
evaluator reproduces the archived scalar results on their original banks.

## 1. Common-instance comparison

All five original configurations now use the same 46 conservative-feasible
instances in the primary matched table. A second table gives paired contrasts
directly, avoiding subtraction of differently conditioned means.

| Customers | Matched count | Original procedure minus conservative speed, percentage points |
|---|---:|---:|
| 20 | 18 | 21.4 |
| 50 | 13 | 17.9 |
| 100 | 8 | 16.0 |
| 200 | 7 | 8.3 |

The n=200 bootstrap interval includes zero. The complete procedure is the
relevant headline contrast; the unscreened slack objective is a separate
ablation. Both remain visible.

## 2. Screening conservative-speed candidates

The conservative-speed distance generator uses the same 0:5:60-minute buffer
grid, screening bank and Wilson admission threshold. Passing plans are ordered
by distance, planned duration, then buffer. Its uncontracted plan is the
fallback; when unavailable, the retained slack-aware plan is used.

It selects on 25/53 instances, and all 25 retain the fresh validation bound.
Its pooled procedure probability is 78.6%, versus 78.9% for the original
procedure. The paired difference is -0.3 percentage points, with a 95%
bootstrap interval of approximately [-5.5, 5.0]. Thus the replacement does not
establish overall superiority. It is particularly strong in the low-noise
cells, but the generator can lose candidates under uniform contraction.

## 3. Uniform padding versus clock information

The 33.333 km/h baseline is renamed conservative-speed throughout. Its
deterministic 100% on-time result is explained by its construction: within the
planned horizon, every arc time is upper-bounded, and FIFO propagates that
bound along a feasible route.

A separate clock-profile-aware approximation uses two 2.5-second row-frozen
matrix solves, initialized from the existing nominal plan. Every output is
retimed and verified against the exact deterministic profile. It returns a
valid plan on 49/53 instances. On those matched subsets, it improves service
probability over nominal distance by 17.2-19.1 points, but remains below the
complete original procedure. This is a limited approximation with a disclosed
scheduling rule, not a claim about the best possible TDVRPTW solver.

## 4. Failure labels and reachability caps

The previous blanket attribution of all 21 failures to infeasibility was
stronger than the retained solver evidence supported. The manuscript now
distinguishes a certificate from a missing plan. A shortest-path relaxation,
including intermediate service time, supplies the earliest-service lower
bound without assuming that rounded distance matrices are metric.

Among the 21 originally unselected instances:

- 17 eventually reach a grid point with a reachability certificate.
- Four have no such certificate through beta=60.
- Eight have at least one no-plan outcome before any certificate, including
  those four. These outcomes remain unresolved; passing the necessary test
  does not prove a global route is feasible.

The capped variant changes only deadlines that would otherwise contract past
direct reachability. Identical models reuse their archived candidates. It
selects on 42/53 instances, compared with 32/53 originally, and 40/42 retain the
validation target. Selection by size changes from 14/20, 8/15, 6/10, 4/8 to
14/20, 10/15, 10/10, 8/8.

Pooled service probability increases from 78.9% to 86.6%. The paired gain is
7.7 points [95% bootstrap interval 3.5, 12.5]. That costs about 2.5% additional
distance, 4.2% scheduled driver time and 0.43 additional vehicles per instance.
At n=200, the fleet difference is 1.88 vehicles, so this improvement cannot be
attributed solely to resource-neutral schedule structure. The larger-size
means exceed 95%, but two selected plans fail the validation lower-bound
criterion and the pooled mean is still below 95%.

## 5. Disturbance mechanism

The entire parameter sweep now uses matched instances and paired intervals.
For independent errors, the original-procedure minus conservative difference
moves from about -3.1 points at sigma=0.10 to +30.5 at sigma=0.30. The first
interval includes zero. The positive advantage at higher noise is strong in
this setting, but it is not monotonically increasing in every rho row: at
rho=0.9, the margin is slightly lower at sigma=0.30 than at 0.20.

The methods remain fixed across the sweep. This measures transfer under
different assumed disturbances; it does not re-screen each method for each
cell and does not identify statistical screening separately from generating
the contracted candidate family.

## 6. Resource and implementation qualifications

Matched resource calculations qualify the earlier apparent dominance. The
original procedure uses slightly more scheduled time at n=20 and slightly
more vehicles at n=100. Scheduled time also embeds each planner's own travel
assumption. A new simulated-duration measure uses the common evaluation model;
the original procedure is not shown to use less realized driver time at every
size. At n=20, its mean simulated time is about 8.5% greater.

The clock-origin explanation is in the reproducibility section. The
fleet-matched initialization is explicit. Absolute-distance comparisons retain
the five-second OR-Tools versus HGS limitation. Evening periods are correctly
described as outside the planned shift: they can still affect stochastic
overruns, so the previous claim that they could never enter evaluation was
removed.

## Verification and remaining scope

Fourteen implementation tests pass. The retained evidence gate checks all
53 instances and 413 available configuration outputs, bank separation,
candidate ordering, visits/capacity, contracted time propagation, certificates,
deterministic guarantees, fleet matching and scalar/archive agreement. The
LaTeX tables and figure are regenerated from the retained JSON records.

External benchmark families, operational calibration, objective-weight and
screening-bank sensitivity, and venue-specific formatting remain future
submission work. The paper does not claim deployment readiness.
The existing author spelling is retained pending confirmation.
