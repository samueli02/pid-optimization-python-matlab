"""웹 앱 없이도 Python 결과, MATLAB 전달 파일, ML 보고서를 저장합니다."""
from pathlib import Path
import csv
import json

import numpy as np
from scipy.io import savemat
from pid_core import validate_config, simulate

ML_FILES = ('dataset.csv', 'ml_report.json', 'optimization_history.json', 'surrogate_predictions.csv')
BASE_EXPORTS = {"config.json", "pid_parameters.mat", "python_results.csv", "metrics.json"}


def export_result(config, directory, optimization=None):
    """선택한 모델·PID·시간 조건의 실제 응답과 MATLAB 입력을 저장합니다."""
    config = validate_config(config)
    if optimization and optimization.get('ml_report') and experiment_context(optimization['config']) != experiment_context(config):
        raise ValueError('학습 조건이 현재 설정과 다릅니다. 다시 학습하세요.')
    result = simulate(config)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "metrics.json").write_text(json.dumps(result["metrics"], ensure_ascii=False, indent=2), encoding="utf-8")
    with (directory / "python_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["t", "y", "u", "e"])
        writer.writerows(zip(result["t"], result["y"], result["u"], result["e"]))
    savemat(directory / "pid_parameters.mat", {
        "Kp": config["pid"]["kp"], "Ki": config["pid"]["ki"], "Kd": config["pid"]["kd"],
        "Tf": config["pid"]["tf"], "num": np.array(config["plant"]["num"]),
        "den": np.array(config["plant"]["den"]), "delay": config["plant"]["delay"],
        "dt": config["sim"]["dt"], "horizon": config["sim"]["horizon"],
        "setpoint": config["sim"]["setpoint"], "objective": config["objective"],
    })
    learning_files = export_learning(optimization, config, directory)
    return {"directory": str(directory), "files": sorted(BASE_EXPORTS | set(learning_files)), "metrics": result["metrics"]}


def experiment_context(config):
    """PID 이득을 제외한 학습 문제. 이 조건이 바뀌면 새 학습이 필요합니다."""
    c = validate_config(config)
    return {'plant': c['plant'], 'sim': c['sim'], 'objective': c['objective'], 'tf': c['pid']['tf']}


def export_learning(optimization, config, directory):
    """학습 당시 조건과 현재 조건을 확인하고 실제 관측 데이터만 내보냅니다.

    수동으로 PID를 바꾼 경우 현재 응답 파일과 학습 최선의 PID는 다를 수
    있으므로 두 설정을 보고서에 함께 남깁니다. 예측값은 별도 CSV입니다.
    """
    directory = Path(directory)
    if not optimization or not optimization.get('ml_report'):
        for filename in ML_FILES:
            (directory / filename).unlink(missing_ok=True)
        return []
    if experiment_context(optimization['config']) != experiment_context(config):
        raise ValueError('학습 조건과 현재 전달함수·시뮬레이션·목적함수·필터 조건이 다릅니다. 다시 학습하세요.')
    directory.mkdir(parents=True, exist_ok=True)
    report = {**optimization['ml_report'], 'experiment': {
        'trained_best_config': optimization['config'], 'exported_config': config,
        'seed': optimization.get('seed'), 'bounds': optimization.get('bounds'),
        'method': optimization.get('method'),
        'note': '학습 보고서는 최근 최적화 실행 기준이며 python_results.csv는 현재 PID 응답입니다.',
    }}
    (directory / 'ml_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (directory / 'optimization_history.json').write_text(json.dumps(optimization.get('history', []), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    schemas = {
        'dataset.csv': ('dataset', ['iteration', 'kp', 'ki', 'kd', 'cost', 'raw_cost', 'stable', 'spectral_radius', 'phase', 'split', 'source']),
        'surrogate_predictions.csv': ('surrogate_predictions', ['kp', 'ki', 'kd', 'actual_log_cost', 'predicted_log_cost', 'predicted_std', 'stable', 'split']),
    }
    for name, (key, fields) in schemas.items():
        with (directory / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(optimization.get(key, []))
    return list(ML_FILES)
