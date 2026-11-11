"""실제 GP 학습·추천 재평가·홀드아웃 분리를 검증한다."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
import pid_core
import pid_ml


class MachineLearningTests(unittest.TestCase):
    @staticmethod
    def model():
        return {"plant": {"num": [1], "den": [1, 1], "delay": 0},
                "pid": {"kp": 0.5, "ki": 0.3, "kd": 0.02, "tf": 0.05},
                "sim": {"dt": 0.04, "horizon": 4, "setpoint": 1}, "objective": "ITAE"}

    def test_real_gp_fit_and_recommendation_evaluated(self):
        calls = []
        original_fit = pid_ml.GaussianProcessRegressor.fit

        def tracked_fit(model, x, y, *args, **kwargs):
            calls.append((np.asarray(x).copy(), np.asarray(y).copy()))
            return original_fit(model, x, y, *args, **kwargs)

        with patch.object(pid_ml.GaussianProcessRegressor, "fit", tracked_fit):
            result = pid_core.optimize(self.model(), budget=18, seed=42)
        self.assertGreater(len(calls), 0)
        self.assertTrue(result["ml_report"]["objective_model_fitted"])
        recommended = [r for r in result["dataset"] if r["phase"] == "optimizing"]
        self.assertGreater(len(recommended), 0)
        row = next(r for r in recommended if r["eligible"])
        c = self.model(); c["pid"].update({k: row[k] for k in ("kp", "ki", "kd")})
        observed = pid_core.simulate(c)["metrics"]
        self.assertAlmostEqual(observed["raw_cost"], row["raw_cost"], places=10)
        self.assertEqual(observed["stable"], row["stable"])

    def test_reproducibility_incumbent_bounds_and_holdout(self):
        a = pid_core.optimize(self.model(), budget=18, seed=17)
        b = pid_core.optimize(self.model(), budget=18, seed=17)
        self.assertEqual(a["config"], b["config"])
        self.assertEqual(a["dataset"], b["dataset"])
        self.assertLessEqual(a["after"]["metrics"]["cost"], a["before"]["metrics"]["cost"])
        self.assertTrue(a["after"]["metrics"]["stable"])
        self.assertEqual(a["evaluations"], 18)
        self.assertEqual(len({tuple(r[k] for k in ("kp", "ki", "kd")) for r in a["dataset"]}), 18)
        for row in a["dataset"]:
            for k, pair in zip(("kp", "ki", "kd"), a["bounds"]):
                self.assertTrue(pair[0] <= row[k] <= pair[1])
        train = set(a["ml_report"]["training_iterations"])
        validation = set(a["ml_report"]["validation_iterations"])
        self.assertTrue(validation)
        self.assertFalse(train & validation)
        self.assertTrue(all(r["split"] == "validation" for r in a["dataset"] if r["iteration"] in validation))
        self.assertFalse(a["ml_report"]["validation"]["used_for_final_selection"])
        json.dumps(a, allow_nan=False)

    def test_eighth_order_input_is_not_replaced_by_default_plant(self):
        c = self.model()
        c["plant"] = {"num": [float(np.prod(np.arange(1, 9)))],
                      "den": np.poly(-np.arange(1, 9)).tolist(), "delay": 0.08}
        result = pid_core.optimize(c, budget=12, seed=9)
        self.assertEqual(len(result["config"]["plant"]["den"]), 9)
        self.assertGreater(result["ml_report"]["recommendations_evaluated"], 0)
        self.assertTrue(result["ml_report"]["constraint_model_fitted"])
        self.assertLessEqual(result["after"]["metrics"]["cost"], result["before"]["metrics"]["cost"])

    def test_tiny_bounds_are_rejected_before_duplicate_sampling(self):
        c = self.model(); c["pid"]["kp"] = 0
        with self.assertRaisesRegex(ValueError, "width"):
            pid_core.optimize(c, bounds=[[0, 1e-14], [0, 5], [0, 5]], budget=12)


if __name__ == "__main__":
    unittest.main()
