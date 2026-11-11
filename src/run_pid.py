"""화면 없이 실행하는 설명용 진입점: Python 최적화 → 파일 전달 → MATLAB 확인.

프로젝트 폴더에서 python src/run_pid.py
실제 적분·미분·폐루프 계산은 주석을 단 pid_core.py에 있습니다.
이 파일은 MATLAB을 자동으로 실행하지 않습니다.
"""
from pathlib import Path
import argparse
import json
import sys

from pid_core import DEFAULT_CONFIG, validate_config, optimize, optimize_nelder_mead
from pid_io import export_result

SCRIPT_DIR = Path(__file__).resolve().parent
# src 폴더 구조와 Python 파일 네 개를 같은 폴더에 둔 구성 모두 지원합니다.
ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "src" else SCRIPT_DIR


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Python PID 계산 및 MATLAB 전달 파일 생성")
    parser.add_argument("--config", type=Path, help="전달함수·PID·시간 조건을 담은 JSON")
    parser.add_argument("--objective", choices=["ITAE", "ISE"], default=None)
    parser.add_argument("--budget", type=int, default=180)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--method", choices=["ml", "nelder-mead"], default="ml",
                        help="기본값 ml: 데이터 생성 → GP 학습 → 기대개선 탐색. nelder-mead는 이전 비교용.")
    parser.add_argument("--out", type=Path, help="결과 폴더. 생략하면 results/python_to_matlab")
    parser.add_argument("--kp-bounds", type=float, nargs=2, default=[0, 10])
    parser.add_argument("--ki-bounds", type=float, nargs=2, default=[0, 5])
    parser.add_argument("--kd-bounds", type=float, nargs=2, default=[0, 5])
    args = parser.parse_args()

    # 1. 사용자가 정한 전달함수를 읽습니다. 계수는 s의 내림차순입니다.
    # 예: s²+3s+2 → den=[1,3,2]. 시간지연은 plant.delay에 따로 지정합니다.
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else DEFAULT_CONFIG
    config = validate_config(config)
    if args.objective:
        config["objective"] = args.objective

    # 2. 여러 Kp, Ki, Kd에서 데이터를 생성하고 머신러닝 모델로 성능을 학습합니다.
    # PID의 I항과 ITAE/ISE는 사다리꼴 적분, D항은 필터를 적용한 후진 차분입니다.
    # 실제 미적분: pid_core.py의 _rollout(), _evaluate(). ML: pid_ml.py.
    # GP 예측으로 후보를 고른 후 실제 시뮬레이션으로 평가한 값만 채택합니다.
    optimizer = optimize if args.method == "ml" else optimize_nelder_mead
    result = optimizer(config, bounds=[args.kp_bounds, args.ki_bounds, args.kd_bounds],
                      seed=args.seed, budget=args.budget)
    if not result["feasible_found"]:
        raise RuntimeError("안정한 PID를 찾지 못했습니다. 모델·탐색 범위·초기값을 확인하세요.")
    best = result["config"]
    response = result["after"]
    gains = best["pid"]

    # 3. 최적화한 값과 같은 모델·시간 조건을 저장합니다.
    # CSV는 MATLAB이 따로 계산한 결과와 비교할 기준 데이터입니다.
    out = args.out.resolve() if args.out else ROOT / "results" / "python_to_matlab"
    out.mkdir(parents=True, exist_ok=True)
    # 생성한 관측 데이터와 학습에 쓰지 않은 검증 예측도 함께 보관합니다.
    export_result(best, out, optimization=result)
    (out / "optimization_history.json").write_text(json.dumps(result['history'], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "optimization.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    # 4. 값을 확인하고 MATLAB에서 run_matlab_check.m을 직접 실행합니다.
    print(f"Kp = {gains['kp']:.16g}\nKi = {gains['ki']:.16g}\nKd = {gains['kd']:.16g}")
    print(f"{best['objective']}: {result['before']['metrics']['cost']:.6f} -> {response['metrics']['cost']:.6f}")
    print(f"Saved: {out}")
    if "ml_report" in result:
        report = result["ml_report"]
        print(f"ML: {report['algorithm']}")
        print(f"Training samples: {report['training_samples']}; ML recommendations evaluated: {report['recommendations_evaluated']}")
    matlab_launcher = ROOT / "src" / "matlab" / "run_matlab_check.m"
    if matlab_launcher.is_file():
        print(f"Next: open {matlab_launcher} in MATLAB and click Run.")
    else:
        print("MATLAB 검증에는 위 Saved 폴더의 config.json과 python_results.csv를 사용하세요.")


if __name__ == "__main__":
    main()
