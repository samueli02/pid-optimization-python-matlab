# PID Lab — 수치 미적분으로 구현하는 PID 자동 조정 실험

소프트웨어랩(EE370) 2026학년도 2학기 개인 Term Project입니다. **3강 적분·미분**을 실제 제어 계산에 적용하고, **4강 행렬**과 **5강 랜덤**을 확장해 사용합니다. Python이 제어 응답과 목적함수를 계산하고 PID 계수를 탐색합니다. MATLAB은 같은 설정을 별도로 계산해 결과를 비교합니다.

전달함수를 입력하고 PID 값을 바꾸면서 계단응답·제어입력·탐색 이력을 확인하는 로컬 프로그램입니다. 기준 제어기와 자동 탐색 결과를 같은 모델에서 비교하며, 좋아진 지표와 나빠진 지표를 함께 보여 줍니다. 기본 대상은 학습용 선형 모델이며 실제 장비에서 식별한 모델은 아닙니다.

## 친구와 공유하는 공개 웹 버전

공개 주소: **https://samuel-pid-lab.pristinecucumber3.chatgpt.site**

별도 비밀번호 없이 접속하는 공개본입니다. 방문자의 브라우저에서 Pyodide의 Python·NumPy·SciPy로 PID 계산과 최적화를 실행하므로 제작자의 PC가 켜져 있을 필요가 없습니다. 처음 열 때 계산 패키지를 내려받아 준비하므로 네트워크와 기기 성능에 따라 잠시 걸릴 수 있습니다. 준비가 끝나면 PID 조절, 전달함수 편집, 자동 최적화와 MATLAB 전달 파일 다운로드를 사용할 수 있습니다.

공개본 소스와 로컬 미리보기 방법은 [`web_public/README.md`](web_public/README.md)에 있습니다. 기존 Python 프로그램과 MATLAB 검증 코드는 그대로 사용할 수 있습니다. 브라우저용 패키지 버전은 PC의 라이브러리 버전과 달라 탐색 결과에 작은 차이가 생길 수 있습니다.

## 먼저 읽을 설명용 코드

화면을 쓰지 않고도 **Python에서 PID 계산·최적화 → MATLAB에 값 적용 → MATLAB에서 응답 확인** 순서로 실행할 수 있습니다. 웹 조절 화면은 같은 계산 엔진을 사용하는 선택 인터페이스입니다.

1. [`src/run_pid.py`](src/run_pid.py): 전달함수 읽기, PID 최적화 호출, MATLAB 전달 파일 저장 순서를 한국어 주석으로 설명합니다.
2. [`src/pid_core.py`](src/pid_core.py): 실제 오차·수치적분·차분 미분·PID 출력·목적함수·최적화 구현입니다.
3. [`src/matlab/run_matlab_check.m`](src/matlab/run_matlab_check.m): Python 결과를 불러와 MATLAB에 적용하고 검증 그래프를 엽니다.
4. [`src/matlab/verify_pid.m`](src/matlab/verify_pid.m): MATLAB이 같은 조건의 응답을 독립적으로 계산하는 함수입니다.

```powershell
python src/run_pid.py
# 사용자 전달함수/목적함수를 선택하는 경우
python src/run_pid.py --config data/default_config.json --objective ISE
```

그다음 MATLAB에서 `src/matlab/run_matlab_check.m`을 열고 Run을 누릅니다. Python은 MATLAB을 자동 실행하지 않습니다. MAT의 Kp·Ki·Kd·Tf와 전달함수를 MATLAB 작업 공간에서 볼 수 있고, 검증은 같은 값이 담긴 JSON을 사용합니다. 직접 모델을 바꾸려면 JSON의 `plant.num`, `plant.den`, `plant.delay`를 수정합니다.

## 제출 정보

| 항목 | 상태 |
|---|---|
| 학번 / 이름 | 제출 전 사용자가 입력 |
| GitHub 저장소 URL | [samueli02/pid-optimization-python-matlab](https://github.com/samueli02/pid-optimization-python-matlab) |
| 계획서 | `TP계획서_학번_이름.pdf`의 인적 사항과 파일명 확인 필요 |
| 발표자료 | `slides/발표구성안.md` 12장 구성안 제공. 발표자료 PDF는 아직 미작성 |
| 발표 영상 | 사용자의 실제 실행·설명 영상 필요. 5분±1분, 실제 데모 30초 이상 |
| 발표 대본 | `video/`의 대본을 실제 녹화 내용과 일치시킬 것 |

과제 안내의 최종 제출은 **2026년 12월 13일 23:59**, 파일명은 `TP_학번_이름.zip`입니다. 사용자 인적 사항, 공개 저장소와 개발 이력, 본인 발표 영상은 임의로 만들어 넣지 않습니다.

## 실행 환경과 설치

실제 Python 결과를 생성한 환경은 Windows 11, Python **3.12.13**, NumPy **2.4.6**, SciPy **1.18.0**, Matplotlib **3.10.9**입니다. MATLAB **R2026b Update 1**에서도 독립 재계산을 실행했습니다. Base MATLAB만으로 실행할 수 있으며, 사용 가능한 Control System Toolbox가 있으면 해당 도구를 자동 사용합니다.

아래 명령은 **이 README가 있는 프로젝트 폴더**를 현재 작업 폴더로 삼아 실행합니다. Python 3.12를 준비한 뒤 새 가상환경을 만들 수 있습니다.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

저장된 벤치마크와 같은 라이브러리 버전을 명시하려면 다음 명령을 사용합니다.

```powershell
python -m pip install numpy==2.4.6 scipy==1.18.0 matplotlib==3.10.9
```

이미 검증된 `sm_env`를 사용하는 현재 PC에서는 `conda activate sm_env` 후 실행해도 됩니다. `.venv`, 실행 파일, 빌드 산출물, `__pycache__`는 제출 소스에 포함하지 않습니다.

## 프로그램 실행

```powershell
python src/app.py
```

브라우저에서 `http://127.0.0.1:8765`가 열립니다. 열리지 않으면 주소를 직접 입력합니다. 서버를 종료하려면 터미널에서 `Ctrl+C`를 누릅니다.

Windows에서는 제공된 `run_pid_lab.cmd`를 실행하는 방법도 있습니다. Python과 필요한 라이브러리는 먼저 설치돼 있어야 합니다.

포트 충돌 시 다음처럼 실행합니다.

```powershell
python src/app.py --port 8766 --no-browser
```

1. 기본 PID 응답을 확인하고, 왼쪽의 (K_p,K_i,K_d)를 바꿔 수동 응답을 비교합니다.
2. ITAE 또는 ISE, 탐색 범위와 예산을 선택하고 자동 최적화를 실행합니다. 결과는 탐색을 시작할 때의 수동 설정과 비교합니다.
3. 응답뿐 아니라 오버슈트, 정착시간, 끝점 오차, 안정성도 함께 확인합니다.
4. 고급 설정에서 전달함수의 분자·분모 계수를 내림차순으로 입력하거나 인수 형태의 모델을 구성합니다. 분자 차수는 분모 차수보다 작아야 합니다.
5. **MATLAB 검증 파일 저장**을 누르면 현재 설정의 JSON·MAT·CSV·지표가 `results/latest/`에 저장됩니다.

최적화는 로컬 Python 프로세스에서 실행됩니다. 기본 UI 탐색 예산은 180회이며 예산은 최대 고유 후보 평가 횟수입니다. 같은 모델·시간 조건·탐색 범위·시드·예산·라이브러리 버전에서 재현성을 확인합니다.

## 기본 모델과 계산 조건

$$
G(s)=\frac{10e^{-0.1s}}{(s+1)(0.3s+1)(0.05s+1)(s^2+0.4s+4)}.
$$

지연을 제외한 분모 계수는 `[0.015, 0.371, 1.556, 3.0, 5.8, 4.0]`입니다. 초기 PID는 `(0.1, 0.05, 0.02)`, 미분 필터 시정수는 (T_f=0.05\,s), 샘플 간격은 (h=0.01\,s), 계산 구간은 30초, 목표값은 1입니다. 초기 플랜트 상태와 지연 큐는 0입니다.

시간지연은 다음 식으로 정수 샘플 수로 반올림하고 해당 길이의 입력 큐로 구현합니다.

$$
m=\left\lfloor L/h+0.5\right\rfloor,\qquad L_{\mathrm{effective}}=mh.
$$

이는 정확한 소수 샘플 지연 모델이 아닙니다. 예를 들어 (L=0.105\,s,h=0.01\,s)이면 유효 지연은 (0.11\,s)입니다. 요청 지연과 실제 적용 지연을 지표에 모두 기록합니다. 계산 종료 시간도 (N=\lfloor T/h+0.5\rfloor)에 따라 (Nh)로 기록합니다.

## 강의의 적분·미분이 사용되는 코드

오차는 (e_k=r-y_k)입니다. PID 적분항은 샘플 사이의 사다리꼴 면적을 직접 누적합니다.

$$
I_0=0,\qquad I_k=I_{k-1}+\frac h2(e_k+e_{k-1}).
$$

미분항은 오차의 후진 유한차분에 1차 필터를 적용합니다. 이상적인 미분의 고주파 증폭을 줄이기 위해 (T_f>0)을 사용합니다.

$$
D_0=0,\qquad
D_k=\frac{T_f}{T_f+h}D_{k-1}+\frac{e_k-e_{k-1}}{T_f+h},
\qquad u_k=K_pe_k+K_iI_k+K_dD_k.
$$

초기 (I_0,D_0)를 0으로 두므로 시작 순간의 미분 킥을 적용하지 않는 초기화 규약입니다. Python과 MATLAB이 이 규약을 똑같이 사용합니다.

선택할 수 있는 목적함수도 사다리꼴 수치적분으로 계산합니다.

$$
J_{\mathrm{ITAE}}=\int_0^T t|e(t)|dt,\qquad
J_{\mathrm{ISE}}=\int_0^T e(t)^2dt.
$$

`src/pid_core.py`의 `_rollout()`에서 PID 적분·미분을, `trapezoid()`와 `_evaluate()`에서 목적함수 적분을 확인할 수 있습니다. 라이브러리의 PID 자동 조정 기능을 호출하는 방식이 아닙니다.

각 샘플의 계산 순서는 **현재 상태로 (y_k) 계산 → (e_k) 계산 → 적분·미분 갱신 → (u_k) 계산 → 지연 큐에서 적용 입력 선택 → 다음 플랜트 상태 계산**입니다. 플랜트는 연속 상태공간에서 ZOH로 변환해 샘플 사이에 입력을 일정하게 유지합니다. SciPy의 `cont2discrete(..., method="zoh")`가 이러한 이산화를 지원합니다. [SciPy 공식 문서](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cont2discrete.html)

## 최적화와 안정성 판정

탐색 변수는 ((K_p,K_i,K_d)), 기본 범위는 각각 `[0,10]`, `[0,5]`, `[0,5]`입니다. 초기 후보·정해진 시작 후보·시드로 생성한 후보를 평가한 뒤 경계가 있는 다중 시작점 Nelder–Mead 탐색을 수행합니다. 초기 제어기를 항상 후보로 남기며 안정 조건을 만족하고 비용을 낮추는 경우에만 갱신합니다. SciPy의 경계 처리는 simplex 꼭짓점을 경계 안으로 제한합니다. [SciPy Nelder–Mead 공식 문서](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-neldermead.html)

안정성은 짧은 시간의 파형이 작아 보이는지로 판단하지 않습니다. 플랜트·활성 PID 상태·오차 기억·지연 큐를 포함한 이산 폐루프 행렬 (A_{cl})을 구성하고 다음 조건을 검사합니다.

$$
\rho(A_{cl})=\max_i|\lambda_i(A_{cl})|<1-10^{-9}.
$$

(K_i=0) 또는 (K_d=0)이면 해당 비활성 상태를 제외하므로 사용하지 않는 적분기 때문에 가짜 (z=1) 극점이 생기지 않습니다. 불안정 후보는 큰 비용으로 표시하고 최적해 갱신에서 제외합니다. 수치 발산 시 유효하지 않은 응답·물리 지표는 `null`로 기록합니다. 이 검사는 **구현된 선형 이산 모델의 점근 안정성**에 관한 것으로, 실제 장비의 안정성 보장은 아닙니다.

## 실제 벤치마크 결과

`results/benchmark/summary.json`에 저장된 실행 결과입니다. 조건은 ITAE, 시드 42, 예산 180회, 30초, (h=0.01\,s)입니다. 해당 PC에서 최적화에 약 **7.90초**가 걸렸으며 실행 시간은 PC에 따라 달라집니다.

| 지표 | 초기 제어기 | 탐색 후 |
|---|---:|---:|
| (K_p) | 0.1 | 0.0482613 |
| (K_i) | 0.05 | 0.1872600 |
| (K_d) | 0.02 | 0.0000399051 |
| ITAE | 57.9982522 | 5.1593247 |
| ISE | 3.9204507 | 1.9311632 |
| 오버슈트 | 0.00% | 9.98% |
| 2% 정착시간 | 30초 내 미정착 | 7.89초 |
| 절대 끝점 오차 | 0.0333412 | 0.0002100 |
| 폐루프 스펙트럴 반지름 | 0.9990277 | 0.9979133 |
| 이산 모델 안정성 | 안정 | 안정 |

ITAE가 **91.10% 감소**했지만 오버슈트는 증가했습니다. 제어입력 제곱 적분도 약 3.1844에서 4.6967로 증가했습니다. 목적함수 하나의 개선이 모든 성능의 개선을 뜻하지 않습니다. 탐색 결과의 (K_d)가 거의 0이므로 이번 조건에서는 **PI에 가까운 제어기**가 선택됐다고 해석합니다.

추가로 같은 탐색 이득에서 (h=0.02,0.01,0.005\,s)를 비교했습니다. ITAE는 각각 5.1578603, 5.1593247, 5.1616751이며 모두 해당 이산 모델에서 안정입니다. 이는 샘플 간격에 대한 민감도 실험입니다. 간격을 바꾸면 디지털 제어기와 지연 큐도 달라지므로 단순한 연속시간 적분 오차만을 분리한 실험은 아닙니다.

실패 사례 (K_p=80,K_i=60,K_d=0)은 스펙트럴 반지름 약 1.03990으로 불안정하며 수치 발산 제한에 도달합니다. `failure_case.json`의 `null` 지표를 0이나 정상 결과로 해석하면 안 됩니다.

## 결과 재생성과 Python 검사

```powershell
python src/run_experiments.py --seed 42 --budget 180
python -m unittest discover -s tests -v
```

첫 명령은 `results/benchmark/`에 지표 JSON·CSV, 초기/탐색 후 응답, 제어입력, 탐색 이력, 샘플 간격 비교 그림을 다시 만듭니다. 같은 폴더의 기존 벤치마크 결과를 덮어씁니다. 명령에서 예산을 생략하면 스크립트 기본값 160을 사용하므로 위 표를 재생성하려면 **180을 명시**해야 합니다.

단위 검사는 1차 플랜트와 P 제어기의 독립적인 해석적 이산 응답, 불안정 판정, 0 제어기의 적분 지표, 잘못된 모델 입력, 초기 후보보다 나빠지지 않는 최적화를 검사합니다. 비교 허용오차는 각 검사 코드에 명시돼 있습니다.

## MATLAB 독립 검증

MATLAB에서 프로젝트 폴더를 현재 폴더로 설정한 뒤 실행합니다.

```matlab
addpath('src/matlab');
verify_pid('results/benchmark/optimized/config.json', ...
           'results/benchmark/optimized/python_results.csv', ...
           'results/benchmark/matlab');
```

GUI에서 내보낸 현재 설정을 비교하려면 다음처럼 경로를 바꿉니다.

```matlab
verify_pid('results/latest/config.json', ...
           'results/latest/python_results.csv', ...
           'results/matlab_latest');
```

MATLAB은 Python의 상태행렬이나 계산된 응답을 재사용해 자기 결과로 삼지 않습니다. 전달함수와 설정을 읽고 플랜트·제어기·지연을 별도로 구성합니다. Control System Toolbox를 사용할 수 있으면 `tf → ss → c2d(...,'zoh')`를 사용합니다. 없으면 다항식 계수에서 제어가능 표준형 (A,B,C,D)를 만들고 아래 행렬지수로 ZOH를 계산합니다.

$$
\exp\left(\begin{bmatrix}A&B\\0&0\end{bmatrix}h\right)
=\begin{bmatrix}A_d&B_d\\0&1\end{bmatrix}.
$$

`expm`은 원소별 지수 `exp`와 다른 행렬지수 함수입니다. [MathWorks `expm` 공식 문서](https://www.mathworks.com/help/matlab/ref/expm.html) · [MathWorks `c2d` 공식 문서](https://www.mathworks.com/help/control/ref/dynamicsystem.c2d.html)

스크립트는 `matlab_results.csv`와 `matlab_comparison.json`을 저장하고 시간·출력·제어입력의 최대 절대차, ITAE/ISE 차이를 기록합니다. 시간 오차 `< 1e-10`, 출력·입력 오차 `< 1e-7`일 때 비교를 통과합니다. `matlab_python_comparison.png`와 편집 가능한 `.fig`는 MATLAB이 직접 그리는 출력·제어입력·두 구현의 차이 그림입니다. MAT 파일은 별도 도구에서 읽을 수 있는 파라미터 묶음이며, 이 검증 스크립트의 입력은 JSON입니다.

**실제 MATLAB 비교: 통과.** `results/benchmark/matlab/matlab_comparison.json`에서 출력 최대 절대차는 **4.44×10⁻¹⁵**, 제어입력 차이는 **8.88×10⁻¹⁶**, ITAE 차이는 **1.80×10⁻¹³**, 시간 차이는 0입니다. 이 PC에서는 Control System Toolbox의 `tf` 함수가 설치돼 있지 않아 **제어가능 표준형 + Base MATLAB `expm` 경로**로 재계산했습니다. 라이선스 존재와 실제 제품 설치 여부를 구분했습니다.

## 파일 구조

```text
PID_TermProject/
  README.md
  requirements.txt
  run_pid_lab.cmd
  TP계획서_학번_이름.pdf
  data/
    default_config.json         # 기본 샘플 입력
    first_order_config.json     # 해석식 비교용 1차 모델
  src/
    app.py                      # 로컬 HTTP 서버·내보내기
    pid_core.py                 # 모델 검증·수치 계산·최적화
    run_experiments.py           # 벤치마크와 그림 재생성
    static/index.html           # 한국어 조작 화면
    matlab/verify_pid.m          # MATLAB 독립 재계산
  tests/test_core.py
  results/
    benchmark/                  # 초기/탐색 후 CSV·지표·그림·실패 사례
      matlab/                   # MATLAB 재계산 CSV·JSON·PNG·FIG
    latest/                     # GUI 내보내기 시 생성
  slides/                       # 현재 12장 구성안, 발표자료 PDF는 후속 작성
  video/                        # 현재 발표 대본, 실제 영상은 사용자 녹화 필요
  etc/                          # 보조 설명·검증 자료
```

## 한계와 확장

- 제한된 예산의 다중 시작점 탐색이며 전역 최적해를 보장하지 않습니다. 탐색 범위·시드·예산·평가 구간이 달라지면 결과가 달라질 수 있습니다.
- 현재 비용은 ITAE 또는 ISE 하나입니다. 오버슈트·제어입력·안정 여유에 대한 별도 제약이나 가중 비용을 추가하는 것이 다음 개선 과제입니다.
- 현재 모델은 SISO 선형·정확한 계수·측정 잡음 없음·포화 없음입니다. 실제 구동기 포화, anti-windup, 센서 잡음, 외란, 모델 불확실성, 비선형성은 검증하지 않았습니다.
- UI의 끝점 오차는 무한시간 정상상태 오차가 아니라 **현재 계산 구간의 마지막 표본 오차**입니다. 정착시간도 현재 구간 안에서 2% 대역을 마지막으로 벗어난 이후의 값이며 이후 모든 시간의 거동을 직접 관측한 값이 아닙니다.
- ZOH 플랜트 변환과 디지털 PID의 시간 간격을 구분해야 합니다. 샘플 간격이 크면 실제 폐루프 거동이 달라집니다. 지연 반올림 오차도 함께 고려해야 합니다.
- Python과 MATLAB의 일치는 구현 간 일관성을 검사합니다. 학습용 플랜트가 실제 장비를 정확히 나타낸다는 증거는 아닙니다.

## AI 활용과 개발 과정

OpenAI Codex를 사용해 문제를 구체화하고 Python 계산 엔진, 한국어 UI, MATLAB 재계산 스크립트, 실험 자동화, 문서 초안을 작성·수정했습니다. 검증에는 독립적인 1차 시스템 해석식, 수치적분의 알려진 값, 활성/비활성 PID 상태와 지연을 포함한 행렬 검산, 고정 시드 반복 실행, 불안정 실패 사례, 샘플 간격 민감도, MATLAB 독립 재계산을 사용했습니다. 수치 근거는 벤치마크 JSON·CSV와 MATLAB 비교 JSON에 남겼습니다.

코드가 생성됐다는 사실이나 화면이 그려졌다는 사실만으로 정확성을 판단하지 않습니다. 사용자는 제출 전에 각 PID 항의 계산 순서, 사다리꼴 적분, 필터 차분, 목적함수, 안정성 판정, 탐색의 한계를 직접 설명할 수 있어야 합니다. 2026-11-11 현재 작업을 계산 엔진·MATLAB 검증, 웹 화면, 실험 결과, 문서 단위로 커밋해 GitHub에 공개했습니다. 이 이력은 이날의 실제 게시 기록이며 과거 개발 날짜로 소급하지 않았습니다. 이후 수정도 실제 변경 단위로 기록합니다.

## 참고자료와 출처

- 사용자 제공 「소프트웨어랩(EE370) 기말 Term Project 안내」, 2026학년도 2학기: 제출물·평가기준·강의 연계 요구 사항.
- 소프트웨어랩 3강 적분·미분, 4강 행렬, 5강 랜덤: 본 프로젝트의 강의 연계 주제. 세부 수식과 구현은 제출 코드에 명시.
- [SciPy `cont2discrete`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cont2discrete.html): 연속 상태공간에서 ZOH 이산화.
- [SciPy Nelder–Mead](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-neldermead.html): 탐색 방법·경계·함수 평가 예산.
- [MathWorks `tf`](https://www.mathworks.com/help/control/ref/tf.html): 전달함수 계수의 내림차순 표현.
- [MathWorks `c2d`](https://www.mathworks.com/help/control/ref/dynamicsystem.c2d.html): ZOH 변환.
- [MathWorks `expm`](https://www.mathworks.com/help/matlab/ref/expm.html): 툴박스 없는 행렬지수 기반 ZOH 구현 근거.

공식 문서 확인일: **2026-11-11**. 외부 측정 데이터나 타인의 PID 자동 조정 코드를 복제한 결과는 사용하지 않았으며, 기본 전달함수는 프로젝트의 명시적 실험 입력입니다.

## 계획서 PDF 재생성

Windows에서 `python -m pip install -r requirements-docs.txt`로 선택 의존성을 설치한 뒤 `src/build_plan.py`의 학번·이름·URL을 수정하고 `python src/build_plan.py`를 실행합니다. 맑은 고딕 글꼴을 사용합니다. 이 의존성은 PID 앱 실행에는 필요하지 않습니다.
