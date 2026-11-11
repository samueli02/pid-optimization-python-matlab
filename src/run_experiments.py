"""Reproduce quantitative results and figures without the GUI or MATLAB."""
from __future__ import annotations
import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
import platform
import time
import sys

import numpy as np
import scipy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pid_core import DEFAULT_CONFIG, simulate, optimize_nelder_mead as optimize
from app import export_result

ROOT = Path(__file__).resolve().parents[1]


def savefig(path):
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=160)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    target = ROOT / "results" / "benchmark"
    target.mkdir(parents=True, exist_ok=True)
    config = deepcopy(DEFAULT_CONFIG)
    start = time.perf_counter()
    result = optimize(config, seed=args.seed, budget=args.budget)
    elapsed = time.perf_counter() - start
    before, after = result["before"], result["after"]
    (target / "optimization.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    export_result(config, target / "baseline")
    export_result(result["config"], target / "optimized")
    with (target / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["case", "kp", "ki", "kd", "itae", "ise", "overshoot_pct", "settling_time", "steady_error", "stable"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for label, c, s in [("baseline", config, before), ("optimized", result["config"], after)]:
            writer.writerow({"case": label, **{k: c["pid"][k] for k in ["kp", "ki", "kd"]}, **{k: s["metrics"].get(k) for k in fields[4:]}})
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    plt.figure(figsize=(9, 4.8))
    plt.plot(before["t"], before["y"], label="Manual baseline", color="#e18b31")
    plt.plot(after["t"], after["y"], label="Python optimized", color="#0891b2")
    plt.axhline(config["sim"]["setpoint"], color="#64748b", linestyle="--", label="Setpoint")
    plt.xlabel("Time (s)"); plt.ylabel("Output"); plt.title("Same plant, different PID gains")
    plt.legend(); plt.grid(alpha=.2); savefig(target / "step_response.png")
    plt.figure(figsize=(9, 4.8))
    plt.plot(before["t"], before["u"], label="Manual baseline", color="#e18b31")
    plt.plot(after["t"], after["u"], label="Python optimized", color="#0891b2")
    plt.xlabel("Time (s)"); plt.ylabel("Control input u"); plt.title("Control effort (no saturation model)")
    plt.legend(); plt.grid(alpha=.2); savefig(target / "control_action.png")
    history = result["history"]
    xs, ys = [], []
    for i, item in enumerate(history):
        if isinstance(item, dict):
            v = item.get("best_cost", item.get("cost", item.get("value")))
            x = item.get("evaluation", item.get("iteration", i+1))
        else:
            v, x = item, i+1
        if v is not None:
            xs.append(x); ys.append(v)
    plt.figure(figsize=(9, 4.8)); plt.plot(xs, ys, color="#0891b2")
    plt.xlabel("Objective evaluations"); plt.ylabel("Best objective"); plt.title("Optimization progress (fixed seed)")
    plt.grid(alpha=.2); savefig(target / "optimization_history.png")
    conv = []
    plt.figure(figsize=(9, 4.8))
    for dt in [.02, .01, .005]:
        c = deepcopy(result["config"]); c["sim"]["dt"] = dt
        s = simulate(c)
        conv.append({"dt":dt, **s["metrics"]})
        plt.plot(s["t"], s["y"], label=f"dt = {dt:g} s")
    plt.xlabel("Time (s)"); plt.ylabel("Output"); plt.title("Sampling sensitivity at fixed optimized gains")
    plt.legend(); plt.grid(alpha=.2); savefig(target / "sampling_convergence.png")
    (target / "sampling_metrics.json").write_text(json.dumps(conv, indent=2), encoding="utf-8")
    bad = deepcopy(config); bad["pid"].update(kp=80, ki=60, kd=0)
    bad_result = simulate(bad)
    (target / "failure_case.json").write_text(json.dumps({"config": bad, "metrics": bad_result["metrics"]}, indent=2), encoding="utf-8")
    summary = {"runtime_seconds":elapsed, "seed":args.seed, "budget":args.budget,
        "python":sys.version.split()[0], "numpy":np.__version__, "scipy":scipy.__version__,
        "matplotlib":matplotlib.__version__, "os":platform.platform(),
        "baseline":before["metrics"], "optimized":after["metrics"], "optimized_pid":result["config"]["pid"],
        "improvement_percent":100*(before["metrics"]["cost"]-after["metrics"]["cost"])/before["metrics"]["cost"],
        "failure_case":bad_result["metrics"], "matlab_validation":"pending"}
    (target / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
