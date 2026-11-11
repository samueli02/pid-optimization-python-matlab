"""Python에서 PID 응답을 계산하고 Kp, Ki, Kd를 최적화하는 핵심 코드.

읽는 순서: DEFAULT_CONFIG → simulate → _rollout → _evaluate → optimize.
_rollout에서는 사다리꼴 적분과 필터를 적용한 차분 미분으로 제어입력을
계산한다. _evaluate는 응답 오차를 다시 적분해 ITAE와 ISE를 구한다.
optimize는 pid_ml의 GP 학습과 기대개선으로 세 이득을 탐색한다.
이전 수치 탐색은 optimize_nelder_mead에 비교용으로 보존한다.
두 탐색 모두 PID 내부의 차분 미분과 목적함수의 기울기를 구분해야 한다.

플랜트는 ZOH로 이산화하고, 각 샘플 사이에는 입력을 일정하게 유지한다.
포화·잡음은 모델에 포함하지 않았다. 안정성은 짧은 응답 그래프만 보고
판단하지 않고 제어기와 시간지연까지 포함한 이산 폐루프 행렬로 검사한다.
MATLAB에 넘길 값은 이 코드가 찾은 PID 이득과 동일한 모델·시간 설정이다.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Callable

import numpy as np
from scipy import optimize as scipy_optimize
from scipy import signal


# 계수는 s의 내림차순이다. 예를 들어 [1, 3, 2]는 s²+3s+2를 뜻한다.
# 기본 모델: 10 exp(-0.1s) / [(s+1)(0.3s+1)(0.05s+1)(s²+0.4s+4)].
# 아래 den은 괄호를 전개한 5차 다항식이다. delay는 분모에 넣지 않고
# 입력 큐로 따로 구현한다. tf는 미분 필터 시정수, dt는 샘플 간격이다.
DEFAULT_CONFIG = {
    "plant": {"num": [10.0], "den": [0.015, 0.371, 1.556, 3.0, 5.8, 4.0], "delay": 0.1},
    "pid": {"kp": 0.1, "ki": 0.05, "kd": 0.02, "tf": 0.05},
    "sim": {"dt": 0.01, "horizon": 30.0, "setpoint": 1.0},
    "objective": "ITAE",
}
STABILITY_MARGIN = 1e-9
UNSTABLE_PENALTY = 1e12


def _finite(value, name):
    """계산에 사용할 수 있는 유한 실수인지 확인한다(NaN·무한대 제외)."""
    if isinstance(value, (bool, str)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not np.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def validate_config(config=None):
    """기본값과 사용자 설정을 합치고, 계산 가능한 형태로 정리한다.

    config를 복사하므로 호출자가 넘긴 사전은 수정하지 않는다. 전달함수는
    분자 차수 < 분모 차수인 엄밀히 진성인 모델만 허용한다. 이는 아래에서
    현재 출력 y[k]를 현재 상태 x[k]만으로 계산하는 갱신 규약에 해당한다.
    """
    config = {} if config is None else config
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    if set(config) - set(DEFAULT_CONFIG):
        raise ValueError("Unknown configuration keys")
    c = deepcopy(DEFAULT_CONFIG)
    for section in ("plant", "pid", "sim"):
        part = config.get(section, {})
        if not isinstance(part, dict) or set(part) - set(c[section]):
            raise ValueError(f"Invalid {section} settings")
        c[section].update(part)
    for key in ("num", "den"):
        value = c["plant"][key]
        if not isinstance(value, (list, tuple, np.ndarray)) or not len(value):
            raise ValueError(f"plant.{key} must be a nonempty coefficient array")
        a = np.array([_finite(v, f"plant.{key}") for v in value])
        a = np.trim_zeros(a, "f")
        if a.size == 0:
            raise ValueError(f"plant.{key} cannot be all zero")
        c["plant"][key] = a.tolist()
    num, den = c["plant"]["num"], c["plant"]["den"]
    if len(num) >= len(den) or len(den) > 13:
        raise ValueError("Use a strictly proper plant of order 1 to 12")
    # 분자·분모를 같은 값으로 나눠 전달함수는 유지하고 분모 선두를 1로 만든다.
    lead = den[0]
    c["plant"]["num"] = [v / lead for v in num]
    c["plant"]["den"] = [v / lead for v in den]
    if not all(np.isfinite(v) for v in c["plant"]["num"] + c["plant"]["den"]):
        raise ValueError("Plant coefficient normalization overflowed")
    for section, keys in (("pid", ("kp", "ki", "kd", "tf")), ("sim", ("dt", "horizon", "setpoint"))):
        for key in keys:
            c[section][key] = _finite(c[section][key], f"{section}.{key}")
    c["plant"]["delay"] = _finite(c["plant"]["delay"], "plant.delay")
    if any(not 0 <= c["pid"][key] <= 1e6 for key in ("kp", "ki", "kd")):
        raise ValueError("PID gains must be between 0 and 1e6")
    if c["pid"]["tf"] <= 0:
        raise ValueError("The derivative-filter time constant tf must be positive")
    dt, horizon = c["sim"]["dt"], c["sim"]["horizon"]
    if not 1e-4 <= dt <= 1 or not dt <= horizon <= 600:
        raise ValueError("Require 0.0001 <= dt <= 1 and dt <= horizon <= 600 seconds")
    # 과도한 배열 크기와 안정성 행렬 크기를 막는 실험 도구의 계산량 제한이다.
    if horizon / dt > 50000:
        raise ValueError("Use at most 50000 simulation intervals")
    if c["sim"]["setpoint"] == 0:
        raise ValueError("Use a nonzero step setpoint for normalized step-response metrics")
    if c["plant"]["delay"] < 0 or _delay_samples(c) > 240:
        raise ValueError("Delay must be nonnegative and at most 240 sample intervals")
    objective = str(config.get("objective", c["objective"])).upper()
    if objective not in ("ITAE", "ISE"):
        raise ValueError("objective must be ITAE or ISE")
    c["objective"] = objective
    return c


def _delay_samples(c):
    # m=floor(L/dt+0.5)로 반올림한다. 실제 적용 지연은 m*dt이므로,
    # 소수 샘플 지연은 근사값이며 요청한 L과 다를 수 있다.
    # Python round()의 짝수 쪽 반올림 대신 MATLAB과 같은 규칙을 명시한다.
    return int(np.floor(c["plant"]["delay"] / c["sim"]["dt"] + 0.5))


@lru_cache(maxsize=32)
def _discretize(num, den, dt):
    """연속 전달함수를 상태공간으로 바꾸고 ZOH로 이산화한다.

    연속식 dx/dt=A x+B u, y=C x+D u를
    이산식 x[k+1]=Ad x[k]+Bd u[k], y[k]=C x[k]로 바꾼다.
    ZOH는 구간마다 u를 일정하게 유지한다는 가정의 변환이며 Euler 근사가
    아니다. 같은 플랜트와 dt는 캐시해 PID 후보마다 변환을 반복하지 않는다.
    """
    a, b, cy, dy = signal.tf2ss(num, den)
    ad, bd, cd, dd, _ = signal.cont2discrete((a, b, cy, dy), dt, method="zoh")
    if not all(np.all(np.isfinite(v)) for v in (ad, bd, cd, dd)):
        raise ValueError("Plant discretization overflowed; check coefficients and sample interval")
    if np.max(np.abs(dd)) > 1e-12:
        raise ValueError("Direct plant feedthrough is unsupported")
    return ad, bd[:, 0], cd[0]


def _plant(c):
    """설정 사전에서 플랜트 계수와 샘플 간격을 꺼내 변환 결과를 받는다."""
    return _discretize(tuple(c["plant"]["num"]), tuple(c["plant"]["den"]), c["sim"]["dt"])


def _closed_loop_matrix(c, discrete):
    """실제로 구현한 디지털 PID와 지연 큐의 폐루프 상태행렬을 만든다.

    상태 z에는 플랜트 x, 필요한 I[k-1]·D[k-1]·e[k-1], 지연 큐를 넣는다.
    기준입력을 0으로 둔 동차식 z[k+1]=Acl z[k]의 고유값이 모두 단위원
    안에 있어야 이산 시스템이 점근 안정하다. 발산이 느린 후보는 30초
    그래프가 멀쩡해 보일 수 있으므로, 최적화에 이 검사가 필요하다.

    Ki=0 또는 Kd=0이면 사용하지 않는 상태는 제외한다. 특히 꺼진 적분항을
    남기면 실제 제어와 무관한 고유값 z=1을 만들어 안정 판정을 왜곡한다.
    """
    ad, bd, cy = discrete
    n, delay = len(bd), _delay_samples(c)
    kp, ki, kd, tf = (c["pid"][k] for k in ("kp", "ki", "kd", "tf"))
    dt = c["sim"]["dt"]
    index, size = {}, n
    for key, active in (("integral", ki != 0), ("derivative", kd != 0), ("previous_error", ki != 0 or kd != 0)):
        if active:
            index[key], size = size, size + 1
    queue_start = size
    size += delay
    a = np.zeros((size, size))
    error = np.zeros(size)
    # 동차식의 기준입력 r=0에서 e=-C*x. 이 행벡터로 PID 각 항을 구성한다.
    error[:n] = -cy
    control = kp * error
    if ki != 0:
        row = dt / 2 * error
        row[index["integral"]] += 1
        row[index["previous_error"]] += dt / 2
        a[index["integral"]] = row
        control += ki * row
    if kd != 0:
        row = error / (tf + dt)
        row[index["derivative"]] += tf / (tf + dt)
        row[index["previous_error"]] -= 1 / (tf + dt)
        a[index["derivative"]] = row
        control += kd * row
    if "previous_error" in index:
        a[index["previous_error"]] = error
    # 플랜트 행에는 지연 큐의 가장 오래된 입력 또는 현재 PID 입력을 연결한다.
    a[:n, :n] = ad
    if delay:
        a[:n, queue_start] += bd
        for j in range(delay - 1):
            a[queue_start + j, queue_start + j + 1] = 1
        a[-1] = control
    else:
        a[:n] += bd[:, None] * control[None, :]
    return a


def trapezoid(values, dt):
    """등간격 표본의 합성 사다리꼴 적분: dt*(f0/2+f1+...+fN/2).

    함수값 사이를 직선으로 보고 각 구간의 사다리꼴 면적을 더한다.
    ITAE에는 t*abs(e)를, ISE에는 e²를 values로 넘긴다.
    """
    a = np.asarray(values, dtype=float)
    return float(dt * (0.5 * a[0] + a[1:-1].sum() + 0.5 * a[-1]))


def _rollout(c, discrete):
    """하나의 PID 설정으로 t=0부터 종료 시각까지 폐루프 응답을 계산한다.

    핵심 순서: 출력 → 오차 → 적분·미분 → 제어입력 → 지연 → 다음 상태.
    반환값 t, y, u, error는 그래프·CSV·성능 계산에 그대로 사용한다.
    """
    ad, bd, cy = discrete
    dt = c["sim"]["dt"]
    steps = int(np.floor(c["sim"]["horizon"] / dt + 0.5))
    t = np.arange(steps + 1, dtype=float) * dt
    y, u, error = (np.full(steps + 1, np.nan) for _ in range(3))
    x = np.zeros(len(bd))
    delay = _delay_samples(c)
    queue = np.zeros(max(1, delay))
    cursor = 0
    reference = c["sim"]["setpoint"]
    kp, ki, kd, tf = (c["pid"][k] for k in ("kp", "ki", "kd", "tf"))
    # 처음에는 I0=D0=0이다. 시작 순간에 미분 킥을 넣지 않는 초기화 규약으로,
    # MATLAB 검증 코드도 같은 규약을 사용한다.
    integral, derivative, previous_error = 0.0, 0.0, reference
    alpha = tf / (tf + dt)
    ok = True
    with np.errstate(over="ignore", invalid="ignore"):
        for k in range(steps + 1):
            # 1) 현재 상태에서 출력 y[k]를 구하고 목표값과의 오차 e[k]를 계산한다.
            y[k] = cy @ x
            error[k] = reference - y[k]
            if k:
                # 2) 적분항 I[k]=I[k-1]+dt*(e[k]+e[k-1])/2.
                #    누적 오차의 사다리꼴 면적이며, 아직 Ki를 곱하지 않은 값이다.
                integral += 0.5 * dt * (error[k] + previous_error)
                # 3) 후진 차분 (e[k]-e[k-1])/dt에 저역통과 필터를 적용한다.
                #    정리하면 D[k]=Tf/(Tf+dt)*D[k-1]+(e[k]-e[k-1])/(Tf+dt).
                #    Tf가 양수인 필터로 이상 미분의 고주파 증폭을 줄인다.
                derivative = alpha * derivative + (error[k] - previous_error) / (tf + dt)
            # 4) P, I, D에 각각 이득을 곱해 더한 것이 시스템에 줄 제어입력이다.
            u[k] = kp * error[k] + ki * integral + kd * derivative
            previous_error = error[k]
            # 수치 발산·과도한 크기는 계산 중단 사유다. 고유값 안정 검사와는 별개다.
            if not np.isfinite(u[k]) or max(abs(y[k]), abs(u[k]), float(np.max(np.abs(x)))) > 1e10:
                ok = False
                break
            if k == steps:
                break
            if delay:
                # 5) 원형 FIFO 큐: 오래된 입력을 꺼내고 현재 u[k]를 그 자리에 저장.
                #    큐 길이가 m이면 플랜트는 m샘플 전의 제어입력을 받는다.
                applied = queue[cursor]
                queue[cursor] = u[k]
                cursor = (cursor + 1) % delay
            else:
                applied = u[k]
            # 6) 선택한 입력을 이번 dt 동안 유지하고 다음 상태 x[k+1]로 진행한다.
            x = ad @ x + bd * applied
    return t, y, u, error, ok


def _evaluate(c, discrete, arrays=True, skip_unstable=False):
    """PID 후보의 안정성, 응답, 적분 목적함수와 부가 성능을 평가한다.

    최적화 중에는 불안정 후보를 먼저 제외해 긴 시뮬레이션을 줄인다.
    비용 cost는 안정·유효한 응답이면 선택한 ITAE 또는 ISE이며,
    불안정·수치 발산 후보에는 큰 벌점을 주어 좋은 해로 선택하지 않는다.
    """
    matrix = _closed_loop_matrix(c, discrete)
    poles = np.linalg.eigvals(matrix)
    # rho=max(|고유값|). rho<1이 안정 조건이며 경계에는 작은 여유를 둔다.
    radius = float(np.max(np.abs(poles)))
    stable = bool(np.isfinite(radius) and radius < 1 - STABILITY_MARGIN)
    if skip_unstable and not stable:
        return {"metrics": {"cost": UNSTABLE_PENALTY + min(radius, 1e6) * 1e6, "stable": False, "spectral_radius": radius}}
    t, y, u, e, ok = _rollout(c, discrete)
    valid = ok and np.all(np.isfinite(y)) and np.all(np.isfinite(u))
    # ITAE=∫t|e|dt는 늦게 남는 오차를, ISE=∫e²dt는 큰 오차를 더 강하게 반영.
    itae = trapezoid(t * np.abs(e), c["sim"]["dt"]) if valid else None
    ise = trapezoid(e * e, c["sim"]["dt"]) if valid else None
    reference = c["sim"]["setpoint"]
    normalized = y / reference
    overshoot = max(0.0, float(np.max(normalized) - 1) * 100) if valid else None
    # 관측 구간에서 목표의 ±2%를 마지막으로 벗어난 다음 샘플을 정착시간으로
    # 표시한다. 구간 끝까지 벗어나 있으면 None(미정착)이며 0초로 쓰지 않는다.
    outside = np.flatnonzero(np.abs(e) > 0.02 * abs(reference)) if valid else np.array([len(t) - 1])
    settling = None
    if stable and valid and (len(outside) == 0 or outside[-1] < len(t) - 1):
        settling = float(t[outside[-1] + 1]) if len(outside) else 0.0
    raw = itae if c["objective"] == "ITAE" else ise
    cost = raw if stable and valid else UNSTABLE_PENALTY + min(radius, 1e6) * 1e6
    # steady_error는 이름과 달리 마지막 표본의 절대 오차다. 무한시간의
    # 엄밀한 정상상태 오차를 측정했다는 뜻은 아니며 정의도 함께 내보낸다.
    metrics = {
        "itae": itae, "ise": ise, "overshoot_pct": overshoot,
        "settling_time": settling, "steady_error": float(abs(e[-1])) if valid else None,
        "final_error": float(e[-1]) if valid else None,
        "final_output": float(y[-1]) if valid else None,
        "cost": float(cost), "raw_cost": raw, "objective": c["objective"],
        "stable": stable, "spectral_radius": radius,
        "stability_method": "spectral radius of the implemented discrete augmented closed loop",
        "stability_margin": STABILITY_MARGIN, "simulation_valid": bool(valid),
        "effective_delay": _delay_samples(c) * c["sim"]["dt"],
        "requested_delay": c["plant"]["delay"], "delay_samples": _delay_samples(c),
        "effective_horizon": float(t[-1]), "settling_band_pct": 2.0,
        "settling_definition": "last exit from the 2% band within the simulated horizon",
        "steady_error_definition": "absolute final-sample error, not an infinite-time guarantee",
        "peak_control": float(np.max(np.abs(u))) if valid else None,
        "control_energy": trapezoid(u * u, c["sim"]["dt"]) if valid else None,
    }
    result = {"metrics": metrics}
    if arrays:
        def json_array(a):
            return [float(v) if np.isfinite(v) else None for v in a]
        result.update(t=t.tolist(), y=json_array(y), u=json_array(u), e=json_array(e), config=deepcopy(c))
    return result


def simulate(config=None):
    """외부에서 호출하는 수동 계산 입구: 설정 검증 → 플랜트 변환 → 응답 평가."""
    c = validate_config(config)
    return _evaluate(c, _plant(c))


def optimize_nelder_mead(config=None, bounds=None, seed=42, budget=240, progress: Callable | None = None):
    """정해진 범위 안에서 ITAE 또는 ISE가 작은 Kp, Ki, Kd를 찾는다.

    1. 현재 수동 PID를 먼저 평가해 비교 기준과 보존할 초기 해로 둔다.
    2. 고정 후보와 seed로 재현되는 난수 후보를 평가해 시작점을 정한다.
    3. 유망한 3개 시작점에서 Nelder-Mead로 주변 이득을 탐색한다.
    4. 안정하고 비용이 더 낮은 후보만 최선의 해로 갱신한다.

    budget은 중복을 제외한 후보의 최대 평가 횟수다. 유한한 범위·예산의
    탐색이므로 전역 최적해를 보장하지 않는다. 미분 이득이 거의 0인
    PI에 가까운 해도 목적함수상 유리하면 정상적인 탐색 결과다.
    """
    c = validate_config(config)
    bounds = np.asarray([[0, 10], [0, 5], [0, 5]] if bounds is None else bounds, dtype=float)
    if bounds.shape != (3, 2) or not np.all(np.isfinite(bounds)) or np.any(bounds[:, 0] < 0) or np.any(bounds[:, 0] >= bounds[:, 1]) or np.any(bounds > 1e6):
        raise ValueError("bounds must contain three finite nonnegative [lower, upper] pairs")
    if isinstance(seed, bool) or int(seed) != seed or not 0 <= int(seed) <= 2**32 - 1:
        raise ValueError("seed must be an integer from 0 to 2^32-1")
    if isinstance(budget, bool) or int(budget) != budget or not 12 <= int(budget) <= 5000:
        raise ValueError("budget must be an integer from 12 to 5000")
    budget, seed = int(budget), int(seed)
    original = np.array([c["pid"][key] for key in ("kp", "ki", "kd")])
    if np.any(original < bounds[:, 0]) or np.any(original > bounds[:, 1]):
        raise ValueError("The initial PID gains must be inside the optimization bounds")
    # 플랜트·dt는 탐색 동안 고정된다. 후보마다 바꾸는 값은 세 PID 이득이다.
    discrete = _plant(c)
    before = _evaluate(c, discrete)
    best_x, best_cost = original.copy(), before["metrics"]["cost"]
    history, cache = [], {}

    class BudgetExhausted(Exception):
        pass

    def evaluate(gains):
        """최적화 알고리즘이 묻는 한 후보의 비용을 계산하고 이력을 저장한다."""
        nonlocal best_x, best_cost
        gains = np.clip(np.asarray(gains, dtype=float), bounds[:, 0], bounds[:, 1])
        # 거의 같은 후보는 캐시를 재사용하며 평가 예산을 다시 소모하지 않는다.
        key = tuple(np.round(gains, 13))
        if key in cache:
            return cache[key]
        if len(cache) >= budget:
            raise BudgetExhausted
        candidate = deepcopy(c)
        candidate["pid"].update(zip(("kp", "ki", "kd"), gains.tolist()))
        metrics = _evaluate(candidate, discrete, arrays=False, skip_unstable=True)["metrics"]
        cost = metrics["cost"]
        # 안정성 통과와 비용 감소를 동시에 만족해야 현재 최선의 해를 교체한다.
        if metrics["stable"] and cost < best_cost:
            best_x, best_cost = gains.copy(), cost
        cache[key] = cost
        entry = {"iteration": len(cache), "cost": float(cost), "best_cost": float(best_cost),
                 "gains": gains.tolist(), "stable": metrics["stable"], "objective": c["objective"]}
        history.append(entry)
        if progress is not None:
            progress(deepcopy(entry))
        return cost

    # 같은 seed는 같은 난수 후보를 만든다. 난수의 세제곱으로 범위 하단 쪽
    # 후보를 더 많이 뽑지만, 최종 결과는 실제 응답 비용으로 비교한다.
    rng = np.random.default_rng(seed)
    starts = [original]
    anchors = ([0.1, 0.05, 0.02], [0.3, 0.1, 0.2], [0.6, 0.2, 0.5], [1.0, 0.3, 1.0])
    starts.extend(np.clip(a, bounds[:, 0], bounds[:, 1]) for a in anchors)
    for _ in range(min(16, max(2, budget // 15))):
        starts.append(bounds[:, 0] + (bounds[:, 1] - bounds[:, 0]) * rng.random(3) ** 3)
    try:
        for start in starts:
            evaluate(start)
        ranked = sorted(starts, key=lambda x: evaluate(x))[:3]
        for number, start in enumerate(ranked):
            remaining = budget - len(cache)
            local_budget = max(8, remaining // (len(ranked) - number))
            # 세 이득을 탐색하므로 simplex는 꼭짓점 4개다. 각 축으로 작은
            # 변화를 준 초기 꼭짓점을 만든 뒤 SciPy가 반사·축소 등을 수행한다.
            simplex = np.tile(start, (4, 1))
            for j in range(3):
                step = max(0.025 * (bounds[j, 1] - bounds[j, 0]), 0.2 * abs(start[j]))
                simplex[j + 1, j] = min(bounds[j, 1], start[j] + step)
                if simplex[j + 1, j] == start[j]:
                    simplex[j + 1, j] = max(bounds[j, 0], start[j] - step)
            # 이 탐색은 목적함수의 기울기를 요구하지 않는다. PID 내부의
            # 차분 미분과 최적화 알고리즘의 기울기 계산은 서로 다른 개념이다.
            scipy_optimize.minimize(evaluate, start, method="Nelder-Mead", bounds=bounds,
                options={"maxfev": local_budget, "maxiter": local_budget, "adaptive": True,
                         "xatol": 1e-5, "fatol": 1e-6, "initial_simplex": simplex})
    except BudgetExhausted:
        pass
    result_config = deepcopy(c)
    result_config["pid"].update(zip(("kp", "ki", "kd"), best_x.tolist()))
    after = _evaluate(result_config, discrete)
    # 마지막에도 같은 수치 계산으로 비교해 원래 수동값보다 나빠지지 않게 한다.
    if after["metrics"]["cost"] > before["metrics"]["cost"]:
        result_config, after = deepcopy(c), deepcopy(before)
    return {"config": result_config, "before": before, "after": after,
            "history": history, "seed": seed, "evaluations": len(cache),
            "budget": budget, "bounds": bounds.tolist(),
            "method": "seeded bounded multistart Nelder-Mead; original controller retained",
            "feasible_found": bool(after["metrics"]["stable"]),
            "improvement_pct": 100 * (before["metrics"]["cost"] - after["metrics"]["cost"]) / max(abs(before["metrics"]["cost"]), 1e-15)}


def optimize(config=None, bounds=None, seed=42, budget=180, progress: Callable | None = None):
    """입력 모델별 데이터를 새로 만들고 GP 기반 Bayesian 최적화를 실행한다.

    기존 수치 계산·안정성 검사는 그대로 재사용한다. 비 ML 비교 방법은
    optimize_nelder_mead()로 별도 보존한다. 지연 import로 순환 import를 막는다.
    """
    from pid_ml import optimize_ml
    return optimize_ml(config, bounds=bounds, seed=seed, budget=budget, progress=progress)


if __name__ == "__main__":
    import json
    print(json.dumps(simulate()["metrics"], indent=2, allow_nan=False))
