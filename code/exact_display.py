"""Exact values for display from the frozen confirmatory analyses.

Both frozen analysis functions (confirm_analysis.analyse and
confirm_analysis_hgs.analyse) round their reported figures to two decimals after
every decision has been made. Rounding such a figure again to one decimal can
differ from rounding the exact value: an exact 27.952 is saved as 27.95, and
27.95 then prints as 27.9 because it is stored as 27.9499... in binary.

exact_analysis() runs the same frozen function with only that display rounding
switched off (every round() call in both modules is display rounding, which
tests/test_exact_display.py checks). The patch is not thread-safe.
check_against() confirms that the exact result agrees with the saved
confirmatory output to within the two-decimal rounding.
"""
from __future__ import annotations


def exact_analysis(module, *args, **kwargs):
    module.round = lambda x, ndigits=None: x
    try:
        return module.analyse(*args, **kwargs)
    finally:
        del module.round


def check_against(exact, saved, path="out", ignore=()):
    """Every field must be present in both; numbers agree to the saved two-decimal
    rounding, and verdicts, counts and other values agree exactly. Top-level keys
    in `ignore` are written by the frozen main() and not by analyse()."""
    if isinstance(exact, dict):
        assert isinstance(saved, dict), path
        extra = set(saved) - set(exact) - set(ignore)
        assert not extra, f"{path}: saved fields {sorted(extra)} were not recomputed"
        for k, v in exact.items():
            assert k in saved, f"{path}.{k} missing from the saved output"
            check_against(v, saved[k], f"{path}.{k}")
    elif isinstance(exact, float) and isinstance(saved, (int, float)):
        assert abs(exact - saved) <= 0.005 + 1e-9, (path, exact, saved)
    else:
        assert exact == saved, (path, exact, saved)
