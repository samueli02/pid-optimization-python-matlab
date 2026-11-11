"""ML PID 학습·독립 예측평가·기존 탐색 비교를 실제 실행해 저장합니다."""
from pathlib import Path
from copy import deepcopy
import argparse
import json
import platform
import time
import sys
import numpy as np
import scipy
import sklearn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pid_core import DEFAULT_CONFIG, optimize, optimize_nelder_mead
from app import export_result

ROOT = Path(__file__).resolve().parents[1]


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--budget', type=int, default=180)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    out = ROOT / 'results' / 'ml_benchmark'
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    result = optimize(DEFAULT_CONFIG, seed=args.seed, budget=args.budget)
    elapsed = time.perf_counter() - start
    export_result(result['config'], out / 'optimized', optimization=result)
    export_result(DEFAULT_CONFIG, out / 'baseline')
    save_json(out / 'optimization.json', result)
    comparison = optimize_nelder_mead(DEFAULT_CONFIG, seed=args.seed, budget=args.budget)
    save_json(out / 'numerical_baseline.json', {
        k: comparison[k] for k in ('config', 'method', 'evaluations', 'budget', 'seed', 'improvement_pct')
    } | {'metrics': comparison['after']['metrics']})
    before, after = result['before'], result['after']
    summary = {'runtime_seconds': elapsed, 'seed': args.seed, 'budget': args.budget,
        'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
        'scikit_learn': sklearn.__version__, 'baseline': before['metrics'], 'ml': after['metrics'],
        'optimized_pid': result['config']['pid'], 'improvement_pct': result['improvement_pct'],
        'ml_report': result['ml_report'], 'numerical_baseline': comparison['after']['metrics'],
        'comparison_note': '같은 총 평가 예산. ML 예산에는 학습/탐색에 쓰지 않는 검증 평가가 포함된다. ML이 항상 더 좋다고 주장하지 않는다.',
        'matlab_validation': 'pending'}
    save_json(out / 'summary.json', summary)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for name, response in [('Manual baseline', before), ('ML selected', after), ('Nelder-Mead reference', comparison['after'])]:
        axes[0].plot(response['t'], response['y'], label=name)
    axes[0].axhline(1, color='gray', ls='--', label='Setpoint')
    axes[0].set(xlabel='Time (s)', ylabel='Output', title='Independent simulated responses')
    axes[0].legend(fontsize=8); axes[0].grid(alpha=.2)
    h = result['history']
    axes[1].plot([p['iteration'] for p in h], [p['best_cost'] for p in h])
    axes[1].set(xlabel='Evaluation', ylabel='Best evaluated cost', title='ML search progress')
    axes[1].grid(alpha=.2)
    fig.tight_layout(); fig.savefig(out / 'ml_response_and_search.png', dpi=180); plt.close(fig)
    points = [p for p in result['surrogate_predictions'] if p['stable'] and p.get('predicted_log_cost') is not None]
    if points:
        actual = np.array([p['actual_log_cost'] for p in points])
        predicted = np.array([p['predicted_log_cost'] for p in points])
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(actual, predicted, color='#0891b2')
        lo, hi = min(actual.min(), predicted.min()), max(actual.max(), predicted.max())
        ax.plot([lo, hi], [lo, hi], '--', color='gray')
        ax.set(xlabel='Actual log(1 + cost)', ylabel='GP prediction', title='Held-out stable candidates (never fitted)')
        ax.grid(alpha=.2); fig.tight_layout(); fig.savefig(out / 'ml_validation.png', dpi=180); plt.close(fig)
    # 입력 전달함수가 달라도 새로 학습하는지 확인하는 별도 실행. 기본 실험과 혼합하지 않습니다.
    first = deepcopy(DEFAULT_CONFIG)
    first['plant'] = {'num': [1.0], 'den': [1.0, 1.0], 'delay': 0.0}
    first['sim']['horizon'] = 8.0
    other = optimize(first, seed=args.seed, budget=40)
    save_json(out / 'different_plant.json', {'config': other['config'], 'before': other['before']['metrics'],
        'after': other['after']['metrics'], 'ml_report': other['ml_report']})
    print(json.dumps({'itae_before': before['metrics']['cost'], 'itae_after': after['metrics']['cost'],
        'improvement_pct': result['improvement_pct'], 'runtime_seconds': elapsed, 'ml_report': result['ml_report']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
