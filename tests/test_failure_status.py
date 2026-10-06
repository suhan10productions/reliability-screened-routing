"""Exercise stage-two dependency handling without solving fresh instances."""
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import study_v7


class FailureStatusTests(unittest.TestCase):
    def test_missing_anchors_preserve_nominal_and_mark_dependents(self):
        record = {
            "instance_seed": 7200, "customers": 20, "vehicles_available": 4,
            "reference_ranges": None,
            "static": {"plan": {"fixture": True}},
            "peak_aware_distance": {"plan": None},
            "weighted_objective_only": {"plan": None},
            "fleet_matched_distance": {"plan": None},
            "screened": {"selected_plan": None},
            "configuration_status": {
                "static": "ok", "peak_aware_distance": "no_plan: fixture",
                "weighted_objective_only": "not_attempted: anchors returned no plan",
                "fleet_matched_distance": "not_attempted: slack-aware plan absent",
            },
        }
        screened = {"selected_plan": None, "procedure_plan": None}
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            # Stub the computational components; run the actual record-building path.
            for name, value in {
                "make_synthetic_instance": object(), "ScenarioBank": object(),
                "screen_generator": screened, "clock_aware": {"plan": None},
                "plan_from_dict": object(), "evaluate": {},
                "audit_old_failure": {"selected": False},
            }.items():
                stack.enter_context(patch.object(study_v7, name, return_value=value))
            study_v7.run(record, folder, 5.0)
            result = json.loads((Path(folder) / "instance_7200.json").read_text())
        self.assertEqual(result["configuration_status"]["nominal"], "ok")
        self.assertIsNotNone(result["configurations"]["nominal"])
        for name in ("slack", "procedure", "capped_procedure"):
            self.assertEqual(result["configuration_status"][name],
                             "not_attempted: anchors returned no plan")
            self.assertIsNone(result["configurations"][name])


if __name__ == "__main__":
    unittest.main()
