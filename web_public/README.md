# 공개 PID·머신러닝 실험실

[공유 주소](https://samuel-pid-lab.pristinecucumber3.chatgpt.site)는 별도 비밀번호 없이 접속합니다. 전달함수를 직접 설정하면 방문자 브라우저의 Python이 데이터를 생성하고 GP를 학습해 PID를 찾습니다. 제작자의 PC나 원격 Python 서버가 계산하지 않습니다.

첫 접속에는 Pyodide **0.29.5**, NumPy·SciPy·scikit-learn 다운로드 시간이 필요합니다. 브라우저 배포본의 scikit-learn은 1.7.0입니다. 각 방문자의 상태와 파일은 분리되며 새로고침하면 조절 상태가 초기화됩니다. 패키지 버전과 기기 성능이 PC용 실행과 달라 결과·소요시간이 달라질 수 있습니다.

| 파일 | 역할 |
|---|---|
| index.html | PID·전달함수 입력, 응답 비교, 학습·검증 지표 |
| python-bridge.js | 화면 요청, 진행 상태, 브라우저 다운로드 |
| pid-worker.js | 별도 Web Worker에서 Python·ML 패키지 로딩 |
| pid_core.py | PC용과 같은 PID 수치 미적분·폐루프 계산 |
| pid_ml.py | GP 학습, 기대개선 후보 선택, 별도 홀드아웃 평가 |
| verify_pid.m | MATLAB에서 설정을 독립적으로 계산 |

## 로컬 미리보기

프로젝트 최상위에서 실행합니다. 이 서버는 정적 파일만 제공합니다.

~~~powershell
python -m http.server 8770 --bind 127.0.0.1 --directory web_public
~~~

http://127.0.0.1:8770을 엽니다. 최초 런타임 로딩에는 인터넷이 필요합니다.

## MATLAB과 학습 자료

**MATLAB 검증 파일 저장**을 누른 뒤 config.json, python_results.csv, pid_parameters.mat, metrics.json을 내려받습니다. ML 실행 기록이 있으면 dataset.csv, ml_report.json, optimization_history.json, surrogate_predictions.csv도 제공합니다. 화면의 MATLAB 코드 링크에서 verify_pid.m을 받아 같은 폴더에 둡니다.

~~~matlab
verify_pid('config.json', 'python_results.csv', 'matlab_result');
openfig(fullfile('matlab_result', 'matlab_python_comparison.fig'), 'visible');
~~~

MAT 파일은 파라미터 묶음이고 검증 함수는 JSON을 읽어 응답을 새로 계산합니다. 이득만 수동 변경하면 응답 CSV는 현재 값, ML 보고서는 최근 학습 기준이며 두 설정은 보고서에 함께 남습니다. 전달함수·시간 조건·목적함수·필터를 바꾸면 이전 학습 기록을 다시 사용할 수 없습니다.

학습에 쓰지 않은 최종 PID 주변의 국소 표본으로 예측 오차를 평가합니다. 이 수치를 전체 이득 범위나 다른 모델에 대한 정확도로 해석하지 않습니다. 자세한 계산·실행 설명은 [프로젝트 README](../README.md)에 있습니다.

출처: [Pyodide Worker](https://pyodide.org/en/stable/usage/webworker.html), [패키지 로딩](https://pyodide.org/en/stable/usage/loading-packages.html), [scikit-learn GP](https://scikit-learn.org/stable/modules/gaussian_process.html).
