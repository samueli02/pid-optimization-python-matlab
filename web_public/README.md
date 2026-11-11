# 공개 PID 실험실

공유 주소: **https://samuel-pid-lab.pristinecucumber3.chatgpt.site**

별도 비밀번호 없이 친구에게 링크를 공유할 수 있는 웹 버전입니다. 계산은 방문자 브라우저 안의 Python에서 실행하며, 제작자의 PC나 Python 서버에 계산 요청을 보내지 않습니다. 처음 접속할 때 Pyodide 0.29.5와 NumPy·SciPy를 내려받으므로 네트워크 상태에 따라 준비 시간이 필요합니다.

## 파일과 계산 흐름

| 파일 | 역할 |
|---|---|
| `index.html` | PID 슬라이더·전달함수 입력·응답 그래프·최적화 비교 화면 |
| `python-bridge.js` | 화면의 요청과 Python 작업자를 연결하고 진행 상태·다운로드 관리 |
| `pid-worker.js` | 별도 Web Worker에서 Pyodide와 수치 패키지를 준비하고 Python 실행 |
| `pid_core.py` | PC용과 같은 PID 계산·수치 미적분·목적함수·이득 탐색 코드 |
| `verify_pid.m` | 내려받은 설정을 MATLAB에서 독립적으로 재계산하는 함수 |

브라우저의 계산 상태와 결과 파일은 방문자마다 분리됩니다. 페이지를 새로고침하면 조절 상태는 초기화됩니다. 동일 계산 코드를 사용하지만 브라우저와 PC의 NumPy·SciPy 버전 차이로 최적화 결과가 조금 달라질 수 있습니다.

## 로컬에서 보기

프로젝트 최상위 폴더에서 아래 명령을 실행합니다. 이 Python 서버는 정적 파일만 제공합니다. 수치 계산은 계속 브라우저의 Python이 담당합니다.

```powershell
python -m http.server 8770 --bind 127.0.0.1 --directory web_public
```

브라우저에서 `http://127.0.0.1:8770`을 엽니다. 최초 패키지 로딩에는 인터넷 연결이 필요합니다.

## MATLAB에서 확인

화면에서 **MATLAB 검증 파일 저장**을 누른 뒤 `config.json`, `python_results.csv`, `pid_parameters.mat`, `metrics.json`을 내려받습니다. 화면의 MATLAB 코드 링크로 `verify_pid.m`도 받아 같은 폴더에 둡니다.

MATLAB에서 해당 폴더를 현재 폴더로 지정하고 실행합니다.

```matlab
verify_pid('config.json', 'python_results.csv', 'matlab_result');
openfig(fullfile('matlab_result', 'matlab_python_comparison.fig'), 'visible');
```

`pid_parameters.mat`은 Kp·Ki·Kd·전달함수를 직접 확인할 때 쓰는 파라미터 묶음입니다. 검증 함수는 `config.json`의 동일 설정으로 응답을 별도로 계산하고 Python CSV와 비교합니다.

Pyodide 참고: [공식 Web Worker 문서](https://pyodide.org/en/stable/usage/webworker.html), [공식 패키지 로딩 문서](https://pyodide.org/en/stable/usage/loading-packages.html).
