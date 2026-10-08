# Revision v38: response to the latest assessment

- Related work: Vareias, Repoussis and Tarantilis (2019) described precisely
  (per-customer chance constraints on assigned windows, two-level ALNS plus exact
  window subproblems), followed by three explicit differences: offered windows
  stay fixed; reliability is a fleet-level service event tested by screening a
  candidate family and validating on a held-out bank; the solver is replaceable,
  and capping removes the direct-reachability obstruction for OR-Tools and HGS.
- Introduction: an explicit list of what the paper does not claim (more reliable
  than robust optimization; 95% with fallbacks; real-traffic reliability; every
  solver; every weighting).
- Design: both studies are "confirmatory within the prespecified synthetic
  setting" and are not external validation.
- Conclusion: "not an artefact of a weak generator" replaced by "persists when
  HGS replaces OR-Tools ... although two generators do not show that it holds
  for every solver"; the robust comparison is framed as a different trade-off.
- Bibliography (checked against Crossref/OpenAlex/DataCite): ghiani2014 title
  now includes "(2003)"; ml4vrp2024 folder is Instances/CVRPTW.
- New `.zenodo.json` so the v3.0 Zenodo record gets the archive title and the
  author "Ali, Suhan" with ORCID. Zenodo's existing records carry GitHub-derived
  titles; edit them on Zenodo (metadata edits keep the DOI).
