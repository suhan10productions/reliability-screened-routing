# V18: target gap and solver limitation

- Conclusion now explains the pooled shortfall: plans admitted by screening
  average 97.3% (original) and 97.4% (capped), while fallback plans average
  50.9% and 45.2%; all 11 capped-procedure fallbacks occur at 20 or 50
  customers. The values are generated macros, and the analysis script stops if
  the "20 or 50 customers" statement ever stops being true.
- Limitations now state the solver gap explicitly: OR-Tools is about 11%
  longer than PyVRP/HGS at 200 customers under an equal five-second budget
  (Table 14), so distance premiums carry solver quality and some uncertified
  screening failures may reflect search limits.
- Checklist gains cover-letter accuracy notes.

Unchanged: all tables, results text, existing macros, raw records and figure.
