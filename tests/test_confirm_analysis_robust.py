import json
import shutil
import tempfile
import unittest
from pathlib import Path

import confirm_analysis_robust as car

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "results" / "robust_capped_dev"


class RobustSafeguardTests(unittest.TestCase):
    """The confirmatory validator must reject incomplete or altered record sets.
    The development records (seed shift 0) serve as a correct set."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for f in DEV.glob("instance_*.json"):
            shutil.copy(f, self.tmp / f.name)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_complete_set_passes(self):
        self.assertEqual(len(car.validate_robust(str(self.tmp), 0)), 45)

    def test_missing_instance_fails(self):
        next(self.tmp.glob("instance_*.json")).unlink()
        with self.assertRaises(SystemExit):
            car.validate_robust(str(self.tmp), 0)

    def test_software_error_file_blocks(self):
        (self.tmp / "software_error_7200.json").write_text("{}")
        with self.assertRaises(SystemExit):
            car.validate_robust(str(self.tmp), 0)

    def test_altered_run_parameter_fails(self):
        f = self.tmp / "instance_7200.json"
        r = json.loads(f.read_text())
        r["iterations"] = 100
        f.write_text(json.dumps(r))
        with self.assertRaises(SystemExit):
            car.validate_robust(str(self.tmp), 0)

    def test_plan_status_mismatch_fails(self):
        f = self.tmp / "instance_7200.json"
        r = json.loads(f.read_text())
        k = next(k for k, v in r["settings"].items() if v["status"] == "ok")
        r["settings"][k]["plan"] = None
        f.write_text(json.dumps(r))
        with self.assertRaises(SystemExit):
            car.validate_robust(str(self.tmp), 0)

    def test_wrong_seed_shift_fails(self):
        with self.assertRaises(SystemExit):
            car.validate_robust(str(self.tmp), 60_000)

    def test_development_mode_reproduces_exploratory_results(self):
        out = car.analyse(car.units_for(car.DEV, False), False)
        self.assertEqual(out["instances"], 45)
        self.assertAlmostEqual(out["R2"]["mean"], 3.634666666666667, places=9)
        self.assertEqual(out["screened_admitted"], 44)


if __name__ == "__main__":
    unittest.main()
