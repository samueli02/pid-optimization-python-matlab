"""화면 없이 실행하는 설명용 진입점: Python 최적화 → 파일 전달 → MATLAB 확인.

프로젝트 폴더에서 python src/run_pid.py
실제 적분·미분·폐루프 계산은 주석을 단 pid_core.py에 있습니다.
이 파일은 MATLAB을 자동으로 실행하지 않습니다.
"""
from pathlib import Path
import argparse
import csv
import json

import numpy as np
from scipy.io import savemat
from pid_core import DEFAULT_CONFIG, validate_config, optimize

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Python PID 계산 및 MATLAB 전달 파일 생성")
    parser.add_argument("--config", type=Path, help="전달함수·PID·시간 조건을 담은 JSON")
    parser.add_argument("--objective", choices=["ITAE", "ISE"], default=None)
    parser.add_argument("--budget", type=int, default=180)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # 1. 사용자가 정한 전달함수를 읽습니다. 계수는 s의 내림차순입니다.
    # 예: s²+3s+2 → den=[1,3,2]. 시간지연은 plant.delay에 따로 지정합니다.
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else DEFAULT_CONFIG
    config = validate_config(config)
    if args.objective:
        config["objective"] = args.objective

    # 2. 여러 Kp, Ki, Kd를 대입하여 폐루프 응답을 계산하고 비용을 비교합니다.
    # PID의 I항과 ITAE/ISE는 사다리꼴 적분, D항은 필터를 적용한 후진 차분입니다.
    # 실제 구현: pid_core.py의 _rollout(), _evaluate(), optimize().
    result = optimize(config, bounds=[[0, 10], [0, 5], [0, 5]],
                      seed=args.seed, budget=args.budget)
    if not result["feasible_found"]:
        raise RuntimeError("안정한 PID를 찾지 못했습니다. 모델·탐색 범위·초기값을 확인하세요.")
    best = result["config"]
    response = result["after"]
    gains = best["pid"]

    # 3. 최적화한 값과 같은 모델·시간 조건을 저장합니다.
    # CSV는 MATLAB이 따로 계산한 결과와 비교할 기준 데이터입니다.
    out = ROOT / "results" / "python_to_matlab"
    out.mkdir(parents=True, exist_ok=True)
    for filename, value in [("config.json", best), ("metrics.json", response["metrics"]),
                            ("optimization_history.json", result["history"])]:
        (out / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "python_results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["t", "y", "u", "e"])
        writer.writerows(zip(response["t"], response["y"], response["u"], response["e"]))
    savemat(out / "pid_parameters.mat", {
        "Kp": gains["kp"], "Ki": gains["ki"], "Kd": gains["kd"], "Tf": gains["tf"],
        "num": np.asarray(best["plant"]["num"]), "den": np.asarray(best["plant"]["den"]),
        "delay": best["plant"]["delay"], "dt": best["sim"]["dt"],
        "horizon": best["sim"]["horizon"], "setpoint": best["sim"]["setpoint"],
    })

    # 4. 값을 확인하고 MATLAB에서 run_matlab_check.m을 직접 실행합니다.
    print(f"Kp = {gains['kp']:.16g}\nKi = {gains['ki']:.16g}\nKd = {gains['kd']:.16g}")
    print(f"{best['objective']}: {result['before']['metrics']['cost']:.6f} -> {response['metrics']['cost']:.6f}")
    print(f"Saved: {out}")
    print("Next: open src/matlab/run_matlab_check.m in MATLAB and click Run.")


if __name__ == "__main__":
    main()
