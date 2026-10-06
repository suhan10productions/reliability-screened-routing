# Reliability-screened routing: model and evidence specification

## Planning and travel

One depot, deterministic demand and service, homogeneous capacitated vehicles,
offered service-start windows, free depot departure, and a 600-minute planned
shift beginning 06:00. Nominal planning is at 40 km/h. Conservative planning
uses 40/1.2 km/h for all arcs and times. Both matrices round travel minutes up.

The original weighted objective combines fuel proportional to distance,
deadline-slack deficit, scheduled driver duration and fleet use. Four
two-second anchor solves provide fixed empirical scaling ranges; no clipping
or Pareto-bound claim is made. Weights are 0.5693, 0.2643, 0.1055, 0.0609.

Evaluation integrates a positive full-day speed profile across boundaries.
Speeds are 40 km/h divided by 0.9 before 07:00, 1.2 from 07:00 to 09:00,
1.0 from 09:00 to 17:00, 1.3 from 17:00 to 19:00, and 0.9 thereafter.
Evening periods are outside the planned shift but can affect stochastic
overruns. Each deterministic arc time is multiplied by a lognormal error
with median one. Baseline sigma is 0.20 and latent Gaussian rho is 0.50.
Multipliers on shared directed arcs are identical within a scenario bank.

The new clock approximation uses two row-frozen matrices based on the
preceding plan's origin departure estimates, with two 2.5-second distance
solves. Every candidate is retimed and verified under the exact deterministic
profile. Its initial nominal plan has an already-incurred separate solve
cost. No exact time-dependent optimization claim is made.

## Screening and contraction

The original uniform upper window is max(l_i,u_i-beta). Offered promises never
change in evaluation. The weighted generator uses beta in 0,5,...,60, a
five-second call, and at most three attempts until the first plan is found.
The selected candidate minimizes the fixed normalized score among passing
candidates. If none passes, the uncontracted slack plan is returned.

Screened conservative uses the identical grid, screening bank and threshold
with a conservative-speed distance generator. Passing candidates are ordered
by distance, planned duration, then beta. The fallback is the uncontracted
conservative plan or the existing slack plan if the former was not found.

The capped variant uses min(u_i,max(l_i,u_i-beta,e_i)), where e_i is earliest
direct service under the nominal planning matrix. Identical contracted models
reuse archived candidates; changed models are solved with the same limit.
A cap protects direct reachability only; it is not a global feasibility
certificate and does not guarantee any stochastic service level.

Diagnostic certificates use a shortest-path lower bound with intermediate
service times included. A contracted deadline earlier than the lower bound
proves infeasibility. Every other absent solver output is a no-plan outcome
with unresolved cause, even if direct service is individually possible.

## Statistical assessment

The event is at least kappa=0.95 of customers on time in a scenario. Admission
requires its one-sided 95% Wilson lower bound to reach alpha=0.95, based on
1,000 scenarios. Selection has no access to the 5,000-scenario fresh validation
bank. The Wilson bound is not a simultaneous coverage guarantee over the
candidate grid. Fresh validation reports compliance and never replaces the
selected plan after seeing its outcome.

All eight configurations share validation draws on each instance. Original
comparisons use the common 46 instances where conservative planning returned
a plan. New clock comparisons disclose any further missing output. Complete
procedures have 53 outputs through their fixed fallbacks. Mean planned costs,
customer outcomes and paired differences use explicitly stated denominators.
Bootstrap intervals use 20,000 instance resamples; they are not simultaneous
across tables or sensitivity cells.

The nine-cell sigma-rho sweep holds plans fixed and uses a separate bank of
1,000 common scenarios per cell. It is exploratory sensitivity on assumed
parameters. It is not external or field validation, nor sensitivity to all
objective weights. Retained old scenarios and seed-labelled fresh scenarios
are both archived for traceability.
