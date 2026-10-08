import glob
import json
import unittest
from pathlib import Path

from misspecification import AltBank, evaluate_alt
from relscreen_v6 import ModelParams, make_synthetic_instance
from relscreen_v7 import plan_from_dict

ROOT = Path(__file__).resolve().parents[1]


def first_per_size(directory):
    """The first stored record for each instance size in a results directory."""
    out = {}
    for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json"))):
        r = json.loads(Path(f).read_text())
        out.setdefault(r["customers"], r)
    return out


class AlternativeEvaluatorTests(unittest.TestCase):
    """Under the paper's model and the validation seed, the evaluator for the
    alternative delay models must reproduce the stored validation results."""

    def check(self, record, configurations):
        params = ModelParams()
        seed = record["instance_seed"]
        data = make_synthetic_instance(record["customers"], record["vehicles_available"], seed)
        bank = AltBank(5000, 400_000 + seed, "baseline")
        checked = 0
        for name, cfg in configurations.items():
            if cfg is None or cfg.get("plan") is None:
                continue
            got = evaluate_alt(plan_from_dict(cfg["plan"]), data, params, bank)
            self.assertAlmostEqual(got, 100 * cfg["validation"]["service_level_success"], places=9,
                                   msg=(seed, name))
            checked += 1
        return checked

    def test_ortools_plans_every_size(self):
        recs = first_per_size("results/v7")
        self.assertEqual(sorted(recs), [20, 50, 100, 200])
        n = sum(self.check(r, {k: r["configurations"][k] for k in ("conservative", "procedure", "capped_procedure")})
                for r in recs.values())
        self.assertGreaterEqual(n, 10)

    def test_hgs_plans_every_size(self):
        recs = first_per_size("results/hgs_dev")
        self.assertEqual(sorted(recs), [20, 50, 100, 200])
        n = sum(self.check(r, {k: r["configurations"][k] for k in ("hgs_conservative", "hgs_capped_cons")})
                for r in recs.values())
        self.assertGreaterEqual(n, 6)

    def test_robust_plans_every_size(self):
        recs = first_per_size("results/robust_capped_dev")
        self.assertEqual(sorted(recs), [20, 50, 100])
        n = sum(self.check(r, {k: r["settings"][k] for k in ("G3_d0.6", "box_d0.6")}) for r in recs.values())
        self.assertGreaterEqual(n, 5)

    def test_stronger_peak_does_not_help(self):
        params = ModelParams()
        r = first_per_size("results/v7")[100]
        data = make_synthetic_instance(r["customers"], r["vehicles_available"], r["instance_seed"])
        plan = plan_from_dict(r["configurations"]["capped_procedure"]["plan"])
        base = evaluate_alt(plan, data, params, AltBank(2000, 700_000 + r["instance_seed"], "baseline"))
        strong = evaluate_alt(plan, data, params, AltBank(2000, 700_000 + r["instance_seed"], "strong_peak"))
        self.assertLessEqual(strong, base)


if __name__ == "__main__":
    unittest.main()
