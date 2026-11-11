# PID Lab: 머신러닝과 수치 미적분으로 PID 찾기

**사용자가 전달함수를 정하면 Python이 응답 데이터를 생성하고 Gaussian Process(GP)를 학습해 PID 값을 찾습니다. 그 값을 MATLAB에 적용해 응답을 독립적으로 확인합니다.** 웹 화면은 같은 계산 코드를 조작하는 인터페이스입니다.

소프트웨어랩(EE370) 개인 Term Project입니다. 3강 적분·미분을 제어 계산에, 7강 머신러닝의 학습·예측 개념을 성능 예측에 응용합니다. GP는 이 프로젝트에서 선택한 확장 방법이며 강의에서 GP를 직접 다뤘다는 뜻은 아닙니다. 기본 전달함수는 직접 정한 학습용 선형 모델이고 실제 장비의 식별 모델이 아닙니다.

- [GitHub 저장소](https://github.com/samueli02/pid-optimization-python-matlab)
- [친구와 공유하는 공개 웹](https://samuel-pid-lab.pristinecucumber3.chatgpt.site): 별도 비밀번호 없음. 처음에는 Python·수치 계산·ML 패키지 다운로드 시간이 필요합니다.
- [브라우저 버전 설명](web_public/README.md): 방문자 기기에서 계산하므로 제작자의 PC를 켜 둘 필요가 없습니다.

## 1. Python 계산 → MATLAB 확인

모든 명령은 이 README가 있는 프로젝트 폴더에서 실행합니다. Python 3.12와 requirements.txt의 NumPy·SciPy·Matplotlib·scikit-learn(1.7 이상, 2 미만)이 필요합니다.

~~~powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
~~~

data/default_config.json을 복사해 분자·분모·지연을 직접 설정합니다. 계수는 **s의 내림차순**이며 분자 차수는 분모 차수보다 작아야 합니다. 다음은 1/(s²+3s+2)의 예입니다.

~~~json
{
  "plant": {"num": [1], "den": [1, 3, 2], "delay": 0.1},
  "pid": {"kp": 0.1, "ki": 0.05, "kd": 0.02, "tf": 0.05},
  "sim": {"dt": 0.01, "horizon": 30, "setpoint": 1},
  "objective": "ITAE"
}
~~~

원하는 JSON 경로를 --config에 지정해 실행합니다.

~~~powershell
python src/run_pid.py --config data/default_config.json --method ml --budget 180 --seed 42
~~~

결과는 results/python_to_matlab/에 저장됩니다. --objective ISE, --out results/my_run, --kp-bounds 0 10, --ki-bounds 0 5, --kd-bounds 0 5로 조건을 바꿀 수 있습니다. 초기 이득은 탐색 범위 안에 있어야 합니다.

그다음 MATLAB에서 **src/matlab/run_matlab_check.m을 열고 Run**을 누릅니다. 기본 결과 폴더의 값을 읽고 비교 그래프를 엽니다. --out을 사용했다면 해당 경로를 직접 지정합니다.

~~~matlab
addpath('src/matlab');
verify_pid('results/my_run/config.json', ...
           'results/my_run/python_results.csv', 'results/my_run/matlab');
openfig('results/my_run/matlab/matlab_python_comparison.fig', 'visible');
~~~

Python은 MATLAB을 자동 실행하지 않습니다. MATLAB은 JSON의 전달함수·PID·시간 조건으로 응답을 새로 계산하며 Python CSV는 두 결과를 비교할 때만 사용합니다. MAT 파일은 파라미터를 직접 읽는 용도입니다. Control System Toolbox가 있으면 tf/ss/c2d, 없으면 Base MATLAB의 제어가능 표준형과 expm으로 ZOH 이산화를 수행합니다.

## 2. 설명할 때 읽을 코드

| 파일 | 설명할 내용 |
|---|---|
| [src/run_pid.py](src/run_pid.py) | 전달함수 입력 → Python 학습·탐색 → MATLAB 전달 파일 저장 |
| [src/pid_core.py](src/pid_core.py) | 오차, 적분·미분, 폐루프 응답, 목적함수, 안정성 판정 |
| [src/pid_ml.py](src/pid_ml.py) | 데이터 생성, GP fit/predict, 다음 후보 선택, 홀드아웃 검증 |
| [src/matlab/run_matlab_check.m](src/matlab/run_matlab_check.m) | Python 결과를 MATLAB에 적용하고 그래프 열기 |
| [src/matlab/verify_pid.m](src/matlab/verify_pid.m) | MATLAB의 독립 응답 계산과 오차 비교 |

## 3. 실제 미분·적분과 ML의 역할

샘플 간격 h, 오차 e[k]=r-y[k]에 대해 구현은 다음과 같습니다. 초기 적분·미분 상태는 0입니다.

~~~text
I[k] = I[k-1] + h*(e[k] + e[k-1])/2
D[k] = Tf/(Tf+h)*D[k-1] + (e[k]-e[k-1])/(Tf+h)
u[k] = Kp*e[k] + Ki*I[k] + Kd*D[k]
~~~

I항은 사다리꼴 누적 적분이고 D항은 저역통과 필터를 적용한 후진 차분입니다. ITAE = ∫t|e(t)|dt 또는 ISE = ∫e(t)²dt도 사다리꼴 적분으로 계산합니다. 이것이 **PID 응답을 계산하는 부분**입니다.

ML은 **다음에 평가할 PID 후보를 고르는 부분**입니다.

1. 입력 모델과 시간 조건을 고정하고 여러 (Kp,Ki,Kd)를 실제 시뮬레이션해 데이터를 만듭니다.
2. 안정·유효한 표본의 log(1+J)를 GP로 학습합니다. 별도 GP는 안정성 지표인 스펙트럴 반지름의 로그를 학습합니다.
3. 예측 평균과 불확실성을 이용한 기대개선(EI)에 안정성 추정값을 반영해 후보를 고릅니다.
4. 추천값을 실제 시뮬레이션과 고유값 검사로 다시 평가합니다. **예측값만으로 최종 PID를 채택하지 않습니다.**
5. 마지막 모델을 동결한 뒤 새로운 검증 후보를 평가합니다. 이 후보는 학습·다음 후보 선택·최종 PID 선택에 넣지 않습니다.

GP는 Matérn 커널을 사용하는 지도학습 회귀 모델입니다. 현재 커널 하이퍼파라미터는 고정하며 fit()이 관측 데이터로 사후 예측을 학습합니다. 일반적인 GP 기능은 [scikit-learn 공식 설명](https://scikit-learn.org/stable/modules/gaussian_process.html), 이 프로젝트의 선택은 pid_ml.py에서 확인합니다.

기존 **Nelder-Mead는 대리모델을 학습하지 않는 수치 탐색**이며 비교용으로 보존했습니다.

~~~powershell
python src/run_pid.py --method nelder-mead --budget 180 --out results/numerical_reference
~~~

## 4. 데이터·검증 결과 읽기

| 결과 파일 | 의미 |
|---|---|
| config.json, pid_parameters.mat | 현재 내보낸 모델·PID·시간 조건 |
| python_results.csv, metrics.json | 현재 PID의 실제 시뮬레이션과 성능 지표 |
| dataset.csv | 실제 후보 평가값과 train/validation 구분. 불안정 벌점은 물리적 오차값이 아님 |
| ml_report.json | 학습 표본 수·알고리즘·검증 오차·학습 당시 설정과 내보낸 설정 |
| surrogate_predictions.csv | 별도 검증 후보의 GP 예측과 실제 log(1+J) |
| optimization_history.json | 평가 순서와 실제로 확인한 최선 비용 |

**홀드아웃은 최종 PID 주변의 국소 검증**입니다. MAE·RMSE·R²는 안정·유효한 검증 표본의 log(1+J)에 대한 값이며 전체 이득 범위나 새로운 전달함수의 정확도를 뜻하지 않습니다. 표본이 부족하거나 R²가 낮으면 예측 성능이 충분하다고 주장할 수 없습니다. 모델·목표값·dt·Tf·목적함수가 바뀌면 새로 학습합니다.

웹에서 이득만 수동 변경한 뒤 저장하면 응답 CSV는 **현재 이득**, ML 보고서는 **최근 학습 실행** 기준입니다. 두 설정은 보고서의 experiment에 함께 기록합니다.

~~~powershell
python src/run_ml_experiments.py --seed 42 --budget 180
python -m unittest discover -s tests -v
~~~

첫 명령은 results/ml_benchmark/에 ML 응답·예측 검증·동일 예산의 Nelder-Mead 비교를 저장합니다. ML 예산에는 홀드아웃 평가가 포함됩니다. 라이브러리 버전과 실제 측정값은 해당 [summary.json](results/ml_benchmark/summary.json)을 기준으로 읽습니다. MATLAB 일치는 그 설정으로 따로 실행한 비교 JSON으로 확인합니다.

기존 [results/benchmark/](results/benchmark/)는 **이전 Nelder-Mead 실험 기록**입니다. 거기에 기록된 ITAE 91.10% 감소와 MATLAB 일치 수치를 ML 결과로 사용하지 않습니다. 자세한 구분은 [기본 실험 해석](etc/기본실험_해석.md)에 있습니다. ML이 같은 예산의 수치 탐색보다 항상 우수하다고 주장하지 않습니다.

2026-11-11 기본 모델, seed 42, 총 평가 예산 180의 실제 측정은 다음과 같습니다.

| 지표 | 수동 기준 | ML 선택 | Nelder-Mead 비교 |
|---|---:|---:|---:|
| ITAE | 57.998252 | 5.454838 | 5.159325 |
| 오버슈트 (%) | 0 | 11.0074 | 9.9764 |
| 2% 정착시간 (s) | 30초 내 미정착 | 9.96 | 7.89 |

ML은 수동 대비 ITAE를 **90.5948%** 줄였지만 이번 실행에서는 Nelder-Mead의 비용이 더 낮았습니다. ML 평가 180개는 학습·탐색 156개와 별도 검증 24개로 나뉩니다. 국소 홀드아웃의 log(1+J) 기준 MAE는 0.035995, RMSE는 0.042758, R²는 0.829458입니다. 비용 GP에는 안정·유효 표본 36개가 사용됐습니다.

이 ML 설정의 [실제 MATLAB 비교](results/ml_benchmark/matlab/matlab_comparison.json)는 출력 최대 차이 **3.33×10⁻¹⁵**, 입력 최대 차이 **5.55×10⁻¹⁶**으로 허용값 1×10⁻⁷을 통과했습니다. 실행 환경은 Python 3.12.13, NumPy 2.4.6, SciPy 1.18.0, scikit-learn 1.9.0, MATLAB R2026b Update 1입니다.

## 5. 화면 사용

~~~powershell
python src/app.py
# 포트를 바꾸는 경우
python src/app.py --port 8766 --no-browser
~~~

기본 주소는 http://127.0.0.1:8765입니다. PID·전달함수·목적함수를 조절하고 ML 최적화를 실행하면 수동 응답과 비교하며 학습 및 검증 정보를 확인할 수 있습니다. **MATLAB 검증 파일 저장**은 results/latest/에 파일을 저장합니다. 공개 웹은 같은 역할의 파일을 브라우저에서 다운로드합니다. 패키지 버전 차이로 브라우저와 PC의 탐색 결과가 달라질 수 있습니다.

## 6. 가정과 한계

- 기본 모델: 10 exp(-0.1s) / [(s+1)(0.3s+1)(0.05s+1)(s²+0.4s+4)]. 초기 PID (0.1,0.05,0.02), Tf=0.05s, dt=0.01s, 관측 30초, 목표값 1입니다.
- 지연은 floor(L/dt+0.5)개의 입력 큐로 근사합니다. 소수 샘플 지연은 반올림되며 실제 적용 지연을 기록합니다.
- 안정성은 활성 PID 상태와 지연을 포함한 이산 폐루프 행렬의 고유값으로 판정합니다. 유한 시간 파형이 작다는 사실만으로 안정이라 하지 않습니다.
- 오버슈트·제어입력 에너지는 비용이 줄어도 증가할 수 있습니다. 끝점 오차는 무한 시간의 정상상태 오차가 아닙니다.
- 유한한 범위·예산·후보 풀의 결과입니다. 전역 최적, 실물 장비 성능, 다른 모델에 대한 일반화를 보장하지 않습니다. 잡음·포화·외란·anti-windup은 현재 검증 범위에 없습니다.
- Python/MATLAB 일치는 같은 이산 계산의 구현 검증이며 모델의 물리적 타당성 검증은 아닙니다.

## 7. 제출과 출처

학번·이름은 사용자가 입력해야 합니다. TP계획서_학번_이름.pdf는 2쪽 계획서이며 slides/발표구성안.md와 video/script.txt는 초안입니다. 제출용 발표자료 PDF와 실제 영상은 별도 제작이 필요합니다. 안내자료 기준 마감은 **2026-12-13 23:59**, 최종 파일명은 TP_학번_이름.zip입니다. [제출 체크리스트](etc/제출체크리스트.md)를 확인하세요.

Codex로 코드·문서 초안을 작성하고 수식 대조, 자동 검사, 실제 실행과 MATLAB 독립 계산으로 검증합니다. ML 결과는 데이터 분리와 실제 예측 오차까지 확인하며 과거 수치 탐색 결과와 구분합니다. AI 사용 사실을 공개하고 실제 수정 단위로 개발 이력을 남깁니다.

- [scikit-learn Gaussian Processes](https://scikit-learn.org/stable/modules/gaussian_process.html): GP 회귀와 예측 불확실성.
- [SciPy ZOH](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cont2discrete.html), [Nelder-Mead](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-neldermead.html).
- [MathWorks c2d](https://www.mathworks.com/help/control/ref/dynamicsystem.c2d.html), [expm](https://www.mathworks.com/help/matlab/ref/expm.html).

GP 공식 문서 확인일: 2026-11-11. 강의 원문은 제공되지 않았으므로 특정 GP 수식이나 코드를 강의에서 배웠다고 인용하지 않습니다. 계획서 재생성은 requirements-docs.txt 설치 후 src/build_plan.py의 학번·이름을 수정하고 python src/build_plan.py를 실행합니다(Windows 맑은 고딕 사용).
