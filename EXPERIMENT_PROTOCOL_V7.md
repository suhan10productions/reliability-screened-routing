# Revision protocol, frozen before new outcomes

The 53 synthetic instances, original customer promises, five-second candidate
budget, 0:5:60 buffer grid, and 1,000-scenario admission bank are retained.
All comparisons disclose feasibility denominators. A fresh 5,000-scenario
validation bank (400000 + instance seed) evaluates every retained plan; a
separate 1,000-scenario bank (500000 + seed) supplies the fixed-plan sigma-rho
sweep. Neither is used to select candidates or change this protocol.

1. Recompute all five existing configurations on the common 46 instances
   where the conservative-speed baseline returned a plan. Report direct paired
   differences and bootstrap intervals, including resources.
2. Call the 33.333 km/h comparator **conservative-speed**, because it pads every
   arc and contains no clock-dependent planning information.
3. Apply the same uniform buffer grid and admission rule to distance-minimizing
   conservative-speed candidates. Select the shortest-distance passing plan,
   breaking ties by planned duration then beta. Use the uncontracted
   conservative plan as fallback, or the existing slack-aware plan if that
   generator supplies no uncontracted plan. Report fallback source explicitly.
4. Test direct-reachability-capped contractions for the original weighted
   generator: u_i(beta)=max(l_i,u_i-beta,e_i), where e_i is earliest direct
   service from the depot at time zero. If these windows equal the original
   uniform windows, reuse the exact archived candidate; otherwise solve again
   under the same five-second / maximum-three-attempt rule. This preserves a
   paired comparison without rerunning identical models for solver noise.
5. Add a clock-profile-aware distance heuristic with two 2.5-second solves.
   Freeze each origin's departure estimate from the preceding plan, integrate
   the actual speed profile to form its outgoing matrix row, then re-solve.
   Evaluate and retime each resulting route under the exact deterministic FIFO
   profile; accept only routes that satisfy offered windows and shift end.
   Choose shortest distance among the deterministically feasible outputs.
   This is a limited-budget approximation, not an exact TDVRPTW optimizer.
6. Diagnose archived no-plan outcomes using a shortest-path travel-time lower
   bound that includes intermediate service. A contracted upper window below
   this bound is a certificate. Other failures remain unclassified no-plan
   outcomes; passing this necessary test does not prove feasibility.
7. Report fixed-plan sensitivity (no re-screening at each sigma-rho cell),
   20,000 paired bootstrap resamples, all-instance procedure means, and matched
   contrasts. Absolute route-cost claims retain the HGS benchmark limitation.

These are exploratory revisions informed by previous aggregate results. A new
scenario bank removes direct reuse of the earlier validation draws, but does
not make the synthetic instance set or the research programme a new external
test set. No claim of preregistration or independent real-world confirmation
is made.
