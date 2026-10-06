# V16: editorial voice

The submission manuscript and the generated results text were revised to the
editorial rules recorded for the author's data centre paper: no scaffolding
openers, the "not X, but Y" construction used at most twice, no rhetorical or
appended-clause headings, and headings that name their subject.

- About 20 contrast constructions ("X rather than Y", "X, not Y") rewritten as
  direct statements. Two are kept deliberately because each prevents a specific
  technical misreading: "scaling ranges, not utopia and nadir points", and the
  clock approximation being "not a departure-dependent callback or an exact
  TDVRPTW optimizer".
- Headings renamed: "Clock-profile knowledge without uniform padding" becomes
  "Clock-aware approximation"; "Reachability certificates and unresolved
  search failures" becomes "Diagnosis of screening failures".
- Em-dashes removed; emphatic fragments such as "This distinction is central"
  and "The gain is not free" rewritten plainly.
- Generated prose was changed in `code/analyse_v7.py`, the single source for it.

Verified unchanged: every number, macro, equation (16) and citation in the
manuscript; all 12 generated tables; `result_macros_v7.tex` and
`summary_v7.json` byte-identical; the original figure; raw records. The only
numeric addition in the results text is "n=200" in a sentence stating that the
interval at that size includes zero, which Table 4 confirms. Both manuscripts
build with no errors, undefined references or overfull lines.
