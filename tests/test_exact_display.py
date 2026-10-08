import ast
import inspect
import unittest

import confirm_analysis
import confirm_analysis_hgs
from exact_display import check_against, exact_analysis


def round_calls(module):
    """Line numbers of round() calls in a module and the function containing each."""
    tree = ast.parse(inspect.getsource(module))
    found = []
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "round":
                    found.append((fn.name, node.lineno))
    return sorted(found, key=lambda x: x[1])


class ExactDisplayTests(unittest.TestCase):
    def test_round_only_used_for_display_in_analyse(self):
        # exact_analysis switches off every round() call in these modules; this
        # holds only while all of them are the display rounding at the end of analyse().
        self.assertEqual(round_calls(confirm_analysis),
                         [("analyse", 259), ("analyse", 260), ("analyse", 272), ("analyse", 275)])
        self.assertEqual(round_calls(confirm_analysis_hgs),
                         [("analyse", 191), ("analyse", 193), ("analyse", 202)])

    def test_patch_is_removed(self):
        try:
            exact_analysis(confirm_analysis_hgs, [], False)
        except Exception:
            pass
        self.assertFalse(hasattr(confirm_analysis_hgs, "round"))
        self.assertEqual(confirm_analysis_hgs.analyse.__globals__.get("round"), None)

    def test_check_against(self):
        check_against({"a": 27.952, "v": "CONFIRMED", "k": 3}, {"a": 27.95, "v": "CONFIRMED", "k": 3})
        with self.assertRaises(AssertionError):
            check_against({"a": 27.952}, {"a": 27.94})
        with self.assertRaises(AssertionError):
            check_against({"v": "CONFIRMED"}, {"v": "NOT CONFIRMED"})
        with self.assertRaises(AssertionError):
            check_against({"a": 1.0}, {"a": 1.0, "b": 2})
        check_against({"a": 1.0}, {"a": 1.0, "mode": "x"}, ignore=("mode",))


if __name__ == "__main__":
    unittest.main()
