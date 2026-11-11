"""Independent checks: exact sampled P response, stability, and optimization."""
import unittest
from copy import deepcopy
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pid_core import DEFAULT_CONFIG, validate_config, simulate, optimize


class CoreTests(unittest.TestCase):
    def first_order(self):
        c = deepcopy(DEFAULT_CONFIG)
        c["plant"] = {"num": [1], "den": [1, 1], "delay": 0}
        c["pid"] = {"kp": 2, "ki": 0, "kd": 0, "tf": .05}
        c["sim"] = {"dt": .01, "horizon": 5, "setpoint": 1}
        return c

    def test_exact_sampled_proportional_response(self):
        c = self.first_order(); r = simulate(c)
        a = np.exp(-c["sim"]["dt"])
        pole = a - 2*(1-a)
        expected = (2/3)*(1-pole**np.arange(len(r["t"])))
        np.testing.assert_allclose(r["y"], expected, atol=1e-9)
        self.assertTrue(r["metrics"]["stable"])

    def test_unstable_closed_loop_rejected(self):
        c = self.first_order(); c["pid"]["kp"] = 500
        r = simulate(c)
        self.assertFalse(r["metrics"]["stable"])

    def test_zero_controller(self):
        c = self.first_order(); c["pid"]["kp"] = 0
        r = simulate(c)
        np.testing.assert_allclose(r["y"], 0)
        self.assertAlmostEqual(r["metrics"]["ise"], 5, places=8)
        self.assertAlmostEqual(r["metrics"]["itae"], 12.5, places=8)

    def test_invalid_plant(self):
        c = self.first_order(); c["plant"]["den"] = [0, 0]
        with self.assertRaises((ValueError, TypeError)):
            validate_config(c)

    def test_optimization_keeps_incumbent(self):
        c = self.first_order()
        r = optimize(c, seed=42, budget=20)
        self.assertLessEqual(r["after"]["metrics"]["cost"], r["before"]["metrics"]["cost"]+1e-9)
        self.assertTrue(r["after"]["metrics"]["stable"])


if __name__ == "__main__":
    unittest.main()
