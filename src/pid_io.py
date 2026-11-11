"""머신러닝 데이터와 검증 보고서를 재현 가능한 파일로 저장합니다."""
from pathlib import Path
import csv
import json

from pid_core import validate_config

ML_FILES = ('dataset.csv', 'ml_report.json', 'optimization_history.json', 'surrogate_predictions.csv')


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
