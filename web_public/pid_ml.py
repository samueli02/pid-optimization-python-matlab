"""입력 전달함수에서 생성한 데이터로 학습하는 실제 GP Bayesian PID 탐색.

학습값은 실측 장비 데이터가 아니라 pid_core의 수치 시뮬레이션 결과다.
GaussianProcessRegressor.fit/predict를 실제 호출하고, 예측 평균과 불확실성의
기대개선(EI)으로 다음 이득을 선택한다. 추천은 반드시 실제 시뮬레이션으로
재평가한다. 별도 검증 표본은 마지막 모델을 동결한 후 생성·평가하며,
학습·획득함수·최종 제어기 선택에 넣지 않는다.
"""
from __future__ import annotations

from copy import deepcopy
import math
import warnings

import numpy as np
import sklearn
from scipy.special import ndtr
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel


ALGORITHM = "GaussianProcessRegressor + Matérn(ν=2.5) + constrained expected improvement"
MODEL_TRAINING_LIMIT = 160
BATCH_SIZE = 8
POOL_SIZE = 512


def _validated_options(config, bounds, seed, budget):
    from pid_core import validate_config
    c = validate_config(config)
    try:
        b = np.asarray([[0, 10], [0, 5], [0, 5]] if bounds is None else bounds, dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError("bounds must be three finite [lower, upper] pairs") from exc
    if b.shape != (3, 2) or not np.all(np.isfinite(b)) or np.any(b[:, 0] < 0) or np.any(b[:, 0] >= b[:, 1]) or np.any(b > 1e6):
        raise ValueError("bounds must be three finite nonnegative [lower, upper] pairs")
    # 중복 키의 13자리 반올림보다 충분히 넓어야 새 표본을 계속 만들 수 있다.
    # 극소 범위를 거절해 초기 설계/홀드아웃의 중복 재시도 무한 반복을 막는다.
    if np.any((b[:, 1]-b[:, 0]) < 1e-9*np.maximum(1.0, np.abs(b[:, 1]))):
        raise ValueError("Each gain bound must have sufficient width: at least 1e-9*max(1,abs(upper))")
    for value, name, lo, hi in ((seed, "seed", 0, 2**32-1), (budget, "budget", 12, 1000)):
        try:
            valid = not isinstance(value, (bool, str)) and np.isfinite(value) and int(value) == value and lo <= value <= hi
        except (ValueError, TypeError, OverflowError):
            valid = False
        if not valid:
            raise ValueError(f"{name} must be an integer between {lo} and {hi}")
    initial = np.array([c["pid"][key] for key in ("kp", "ki", "kd")])
    if np.any(initial < b[:, 0]) or np.any(initial > b[:, 1]):
        raise ValueError("The initial PID gains must be inside the optimization bounds")
    return c, b, int(seed), int(budget), initial


def _model_scales(c, bounds, initial):
    """특정 기본 플랜트의 정답 이득 대신 입력 모델의 주파수 척도를 사용한다."""
    from scipy import signal
    poles = np.roots(c["plant"]["den"])
    frequencies = np.abs(poles[np.abs(poles) > 1e-9])
    omega = float(np.median(frequencies)) if len(frequencies) else 1.0
    tau = np.clip(1.0 / max(omega, 1e-6), c["sim"]["dt"], c["sim"]["horizon"])
    w = np.geomspace(max(omega / 30, 1e-5), max(omega * 30, 1e-4), 48)
    with np.errstate(all="ignore"):
        _, response = signal.freqresp((c["plant"]["num"], c["plant"]["den"]), w)
    magnitude = np.abs(response[np.isfinite(response)])
    sensitivity = float(np.max(magnitude)) if len(magnitude) else 1.0
    kp_scale = 0.3 / max(sensitivity, 1e-9)
    scales = np.array([kp_scale, kp_scale / tau, kp_scale * tau])
    # 로그 좌표가 범위 하단도 분해하도록 하되 0과 좁은 범위에서도 유한하다.
    width = bounds[:, 1] - bounds[:, 0]
    scales = np.maximum(scales, np.maximum(np.abs(initial) * 0.25, width * 1e-5))
    return np.clip(scales, width * 1e-5, width)


class _GainCoordinates:
    def __init__(self, bounds, scales):
        self.bounds = bounds
        self.scales = scales
        self.log_span = np.log1p((bounds[:, 1] - bounds[:, 0]) / scales)

    def encode(self, gains):
        x = np.clip(np.asarray(gains), self.bounds[:, 0], self.bounds[:, 1])
        return np.log1p((x - self.bounds[:, 0]) / self.scales) / self.log_span

    def decode(self, coordinates):
        z = np.clip(np.asarray(coordinates), 0, 1)
        return self.bounds[:, 0] + self.scales * np.expm1(z * self.log_span)


def _new_gp(seed):
    # 커널 형태·척도는 고정한다. fit은 관측값으로 사후 평균/공분산을 실제 학습한다.
    # 하이퍼파라미터 재최적화는 브라우저 비용을 줄이기 위해 수행하지 않는다.
    kernel = ConstantKernel(1.0, constant_value_bounds="fixed") * Matern(
        length_scale=[0.22, 0.22, 0.22], length_scale_bounds="fixed", nu=2.5
    ) + WhiteKernel(noise_level=1e-5, noise_level_bounds="fixed")
    return GaussianProcessRegressor(kernel=kernel, alpha=1e-8, normalize_y=True,
                                    optimizer=None, random_state=seed)


def _subsample(rows, maximum, include_best=False):
    if len(rows) <= maximum:
        return rows
    indexes = list(np.linspace(0, len(rows)-1, maximum, dtype=int))
    if include_best:
        best = min(range(len(rows)), key=lambda i: rows[i]["cost"])
        indexes[-1] = best
    return [rows[i] for i in sorted(set(indexes))]


def _fit_models(rows, coordinates, seed):
    """검증 행은 받지 않는다. 비용 회귀는 안정·유효 행만, 극점 회귀는 전부 사용."""
    training = [row for row in rows if row["split"] == "train"]
    safety_rows = _subsample(training, MODEL_TRAINING_LIMIT)
    good_rows = _subsample([row for row in training if row["eligible"]], MODEL_TRAINING_LIMIT, True)
    safety = _new_gp(seed)
    xs = coordinates.encode([[row[k] for k in ("kp", "ki", "kd")] for row in safety_rows])
    ys = np.log(np.maximum([row["spectral_radius"] for row in safety_rows], 1e-12))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        safety.fit(xs, ys)
    objective = None
    if len(good_rows) >= 2:
        objective = _new_gp(seed)
        x = coordinates.encode([[row[k] for k in ("kp", "ki", "kd")] for row in good_rows])
        y = np.log1p([row["raw_cost"] for row in good_rows])
        objective.fit(x, y)
    return objective, safety, good_rows, safety_rows


def _candidate_pool(rng, coordinates, best, progress_fraction):
    center = coordinates.encode(best)
    # 전체 범위와 현재 최선 주변을 함께 검토한다. 이 난수는 후보 풀 생성용이며
    # 다음 실제 평가 후보의 선택은 학습 GP의 획득함수가 담당한다.
    local_count = POOL_SIZE // 2
    local_scale = max(0.018, 0.12 * (1-progress_fraction))
    local = center + rng.normal(0, local_scale, size=(local_count, 3))
    global_log = rng.random((POOL_SIZE // 3, 3))
    global_linear = coordinates.encode(rng.uniform(coordinates.bounds[:, 0], coordinates.bounds[:, 1], size=(POOL_SIZE-local_count-len(global_log), 3)))
    pool_z = np.clip(np.vstack([local, global_log, global_linear]), 0, 1)
    # PI/PD/P 같은 경계해를 제외하지 않는다.
    pool_z[:9] = center
    for j in range(3):
        pool_z[3*j, j] = 0
        pool_z[3*j+1, j] = np.clip(center[j]+local_scale, 0, 1)
        pool_z[3*j+2, j] = np.clip(center[j]-local_scale, 0, 1)
    return coordinates.decode(pool_z)


def _acquisition(objective, safety, z, best_raw, iteration):
    margin_mean, margin_std = safety.predict(z, return_std=True)
    feasibility = ndtr((math.log(1-1e-9)-margin_mean) / np.maximum(margin_std, 1e-12))
    if objective is None or best_raw is None:
        return feasibility + 0.1 * margin_std / max(float(np.max(margin_std)), 1e-12)
    mean, std = objective.predict(z, return_std=True)
    sigma = np.maximum(std, 1e-12)
    delta = math.log1p(best_raw) - mean - 0.005
    normalized = delta / sigma
    ei = delta * ndtr(normalized) + sigma * np.exp(-0.5 * normalized**2) / math.sqrt(2*math.pi)
    return np.maximum(ei, 0) * feasibility


def optimize_ml(config=None, bounds=None, seed=42, budget=180, progress=None):
    from pid_core import _plant, _evaluate
    c, bounds, seed, budget, initial = _validated_options(config, bounds, seed, budget)
    rng = np.random.default_rng(seed)
    coordinates = _GainCoordinates(bounds, _model_scales(c, bounds, initial))
    discrete = _plant(c)
    before = _evaluate(c, discrete)
    best = initial.copy()
    best_cost = before["metrics"]["cost"]
    rows, history, cache = [], [], set()
    recommendations = 0
    fit_count = 0
    validation_budget = min(24, max(2, budget // 6))
    training_budget = budget - validation_budget
    sampling_budget = min(training_budget-1, max(6, min(32, budget // 4)))

    def key(gains):
        return tuple(np.round(np.asarray(gains), 13))

    def report(phase, row=None):
        if progress is None:
            return
        item = deepcopy(history[-1]) if history else {"iteration": 0, "cost": best_cost, "best_cost": best_cost,
            "gains": best.tolist(), "stable": before["metrics"]["stable"], "objective": c["objective"]}
        item.update(phase=phase, training_samples=sum(r["split"] == "train" for r in rows),
                    recommendations_evaluated=recommendations, model_fit_count=fit_count)
        progress(item)

    def evaluate(gains, phase, source, split="train", known_metrics=None):
        nonlocal best, best_cost, recommendations
        gains = np.clip(np.asarray(gains, dtype=float), bounds[:, 0], bounds[:, 1])
        if key(gains) in cache:
            return None
        candidate = deepcopy(c)
        candidate["pid"].update(zip(("kp", "ki", "kd"), gains.tolist()))
        metrics = known_metrics if known_metrics is not None else _evaluate(candidate, discrete, arrays=False, skip_unstable=True)["metrics"]
        raw = metrics.get("raw_cost")
        eligible = bool(metrics["stable"] and raw is not None and np.isfinite(raw) and metrics.get("simulation_valid", True))
        row = {"iteration": len(rows)+1, **dict(zip(("kp", "ki", "kd"), gains.tolist())),
            "cost": float(metrics["cost"]), "raw_cost": float(raw) if raw is not None and np.isfinite(raw) else None,
            "stable": bool(metrics["stable"]), "eligible": eligible,
            "spectral_radius": float(metrics["spectral_radius"]), "phase": phase, "split": split, "source": source}
        # 독립 검증 데이터로 제어기를 재조정하지 않는다.
        if split == "train" and eligible and row["cost"] < best_cost:
            best, best_cost = gains.copy(), row["cost"]
        rows.append(row)
        cache.add(key(gains))
        if phase == "optimizing":
            recommendations += 1
        history.append({"iteration": len(rows), "cost": row["cost"], "best_cost": float(best_cost),
                        "gains": gains.tolist(), "stable": row["stable"], "objective": c["objective"],
                        "phase": phase, "split": split, "source": source})
        report(phase, row)
        return row

    # 모델에서 유도한 척도에 P/PI/PID와 저·고이득 후보를 자동 생성한다.
    evaluate(initial, "sampling", "manual_incumbent", known_metrics=before["metrics"])
    scale = coordinates.scales
    seeds = [bounds[:, 0], [scale[0], 0, 0], [scale[0]*0.5, scale[1]*0.5, 0],
             [scale[0], scale[1], scale[2]*0.1], [scale[0]*2, scale[1]*2, 0], scale]
    for gains in seeds:
        if len(rows) >= sampling_budget:
            break
        evaluate(gains, "sampling", "model_scaled_initial_design")
    while len(rows) < sampling_budget:
        gains = coordinates.decode(rng.random(3)) if len(rows) % 3 else rng.uniform(bounds[:, 0], bounds[:, 1])
        evaluate(gains, "sampling", "space_filling_initial_design")

    objective = safety = None
    good_rows = safety_rows = []
    while len(rows) < training_budget:
        report("training")
        objective, safety, good_rows, safety_rows = _fit_models(rows, coordinates, seed)
        fit_count += 1 + int(objective is not None)
        report("training")
        # 한 번 학습한 모델로 최대 8개를 추천한 뒤 실제 새 관측으로 재학습한다.
        for _ in range(min(BATCH_SIZE, training_budget-len(rows))):
            pool = _candidate_pool(rng, coordinates, best, len(rows)/training_budget)
            pool = np.array([g for g in pool if key(g) not in cache])
            if not len(pool):
                continue
            z = coordinates.encode(pool)
            current_best_raw = best_cost if any(r["eligible"] and r["split"] == "train" for r in rows) else None
            acquisition = _acquisition(objective, safety, z, current_best_raw, len(rows))
            picked = pool[int(np.argmax(acquisition))]
            evaluate(picked, "optimizing", "gp_constrained_expected_improvement")

    # 최종 학습은 train 표본만 사용한다. 이후 모든 검증 예측을 먼저 고정한다.
    report("training")
    objective, safety, good_rows, safety_rows = _fit_models(rows, coordinates, seed)
    fit_count += 1 + int(objective is not None)
    report("validation")
    validation_points = []
    held_keys = set()
    while len(validation_points) < validation_budget:
        point = coordinates.decode(coordinates.encode(best) + rng.normal(0, 0.035, 3))
        if key(point) not in cache and key(point) not in held_keys:
            validation_points.append(point)
            held_keys.add(key(point))
    vx = coordinates.encode(validation_points)
    if objective is not None:
        predicted, deviations = objective.predict(vx, return_std=True)
    else:
        predicted = deviations = [None] * validation_budget
    predictions = []
    for i, point in enumerate(validation_points):
        row = evaluate(point, "validation", "frozen_model_local_holdout", split="validation")
        predictions.append({**dict(zip(("kp", "ki", "kd"), point.tolist())),
            "iteration": row["iteration"], "actual_log_cost": math.log1p(row["raw_cost"]) if row["eligible"] else None,
            "predicted_log_cost": float(predicted[i]) if predicted[i] is not None else None,
            "predicted_std": float(deviations[i]) if deviations[i] is not None else None,
            "stable": row["stable"], "split": "validation"})
    scored = [p for p in predictions if p["actual_log_cost"] is not None and p["predicted_log_cost"] is not None]
    residual = np.array([p["predicted_log_cost"]-p["actual_log_cost"] for p in scored])
    truth = np.array([p["actual_log_cost"] for p in scored])
    mae = float(np.mean(np.abs(residual))) if len(scored) else None
    rmse = float(np.sqrt(np.mean(residual**2))) if len(scored) else None
    variance = float(np.sum((truth-truth.mean())**2)) if len(scored) >= 2 else 0
    r2 = float(1 - np.sum(residual**2)/variance) if variance > 1e-12 else None
    limitations = [
        "학습 데이터는 입력 선형 모델의 시뮬레이션이며 실제 장비 측정이 아닙니다.",
        "제한된 예산·후보 풀의 Bayesian 탐색으로 전역 최적해를 보장하지 않습니다.",
        "고정 Matérn 커널을 사용하며 커널 하이퍼파라미터를 자동 재최적화하지 않습니다.",
        "검증은 최종 제어기 주변의 독립 국소 표본이며 전체 이득 범위의 예측 정확도를 보장하지 않습니다.",
        "홀드아웃 표본은 누수를 막기 위해 학습·획득함수·최종 제어기 선택에서 제외합니다.",
    ]
    sufficient = len(scored) >= 5 and r2 is not None and r2 > 0
    if not sufficient:
        limitations.append("검증 안정 표본이 적거나 R²가 낮아 대리모델 예측 성능이 충분하다고 주장할 수 없습니다.")
    if objective is None:
        limitations.append("안정·유효 학습 표본이 2개 미만이어서 비용 GP는 학습하지 못했고 안정성 GP만 사용했습니다.")
    result_config = deepcopy(c)
    result_config["pid"].update(zip(("kp", "ki", "kd"), best.tolist()))
    after = _evaluate(result_config, discrete)
    if after["metrics"]["cost"] > before["metrics"]["cost"]:
        result_config, after = deepcopy(c), deepcopy(before)
    training_iterations = sorted(set(r["iteration"] for r in good_rows+safety_rows))
    validation = {"n_total": len(predictions), "n_stable": sum(p["stable"] for p in predictions),
        "n_scored": len(scored), "mae_log_cost": mae, "rmse_log_cost": rmse, "r2_log_cost": r2,
        "held_out": True, "used_for_training": False, "used_for_acquisition": False,
        "used_for_final_selection": False, "performance_sufficient": sufficient,
        "note": "최종 GP를 동결한 뒤 최선 이득 주변에서 새로 생성한 국소 홀드아웃. 오차 단위는 log(1+목적함수)입니다."}
    ml_report = {"algorithm": ALGORITHM, "sklearn_version": sklearn.__version__,
        "training_samples": sum(r["split"] == "train" for r in rows),
        "stable_training_samples": sum(r["split"] == "train" and r["eligible"] for r in rows),
        "model_training_samples": len(good_rows), "constraint_training_samples": len(safety_rows),
        "recommendations_evaluated": recommendations, "model_fit_count": fit_count,
        "objective_model_fitted": objective is not None, "constraint_model_fitted": True,
        "kernel": str(objective.kernel_ if objective is not None else safety.kernel_),
        "batch_size": BATCH_SIZE, "candidate_pool_size": POOL_SIZE,
        "training_window_limit": MODEL_TRAINING_LIMIT, "hyperparameter_optimization": False,
        "training_iterations": training_iterations,
        "validation_iterations": [p["iteration"] for p in predictions], "validation": validation,
        "data_description": "입력 전달함수·지연·dt·목표값·Tf·목적함수를 고정하고 PID만 바꿔 생성한 새 시뮬레이션 데이터. 비용 GP는 안정·유효 표본의 log(1+cost), 제약 GP는 log(스펙트럴 반지름)를 학습합니다.",
        "limitations": limitations}
    return {"config": result_config, "before": before, "after": after, "history": history,
        "seed": seed, "evaluations": len(rows), "budget": budget, "bounds": bounds.tolist(),
        "method": ALGORITHM, "feasible_found": bool(after["metrics"]["stable"] and after["metrics"].get("simulation_valid", False)),
        "improvement_pct": 100*(before["metrics"]["cost"]-after["metrics"]["cost"])/max(abs(before["metrics"]["cost"]), 1e-15),
        "ml_report": ml_report, "dataset": rows, "surrogate_predictions": predictions}
