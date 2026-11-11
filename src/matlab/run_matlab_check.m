% Python에서 구한 PID를 MATLAB에 적용하는 실행 스크립트입니다.
% 먼저 프로젝트 폴더에서 python src/run_pid.py 를 실행하세요.
% 그다음 MATLAB에서 이 파일을 열고 Run을 누르세요.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fileparts(fileparts(scriptDir));
inputDir = fullfile(projectDir, 'results', 'python_to_matlab');
outputDir = fullfile(projectDir, 'results', 'matlab_manual');
assert(isfile(fullfile(inputDir, 'config.json')), ...
    'Run Python src/run_pid.py first.');
addpath(scriptDir);

% MATLAB 작업 공간에서 Python의 Kp, Ki, Kd와 전달함수를 바로 확인합니다.
parameters = load(fullfile(inputDir, 'pid_parameters.mat'));
Kp = parameters.Kp;
Ki = parameters.Ki;
Kd = parameters.Kd;
Tf = parameters.Tf;
num = parameters.num;
den = parameters.den;
fprintf('Python result: Kp=%.12g, Ki=%.12g, Kd=%.12g\n', Kp, Ki, Kd);

% 동일 전달함수와 샘플 간격으로 MATLAB이 응답을 별도로 계산합니다.
% verify_pid 내부에서 JSON의 같은 PID 값을 적용합니다.
% CSV는 그래프를 겹쳐 비교하는 데만 사용하며 MATLAB 응답 계산에는 쓰지 않습니다.
verification = verify_pid(fullfile(inputDir, 'config.json'), ...
    fullfile(inputDir, 'python_results.csv'), outputDir);
disp(verification.comparison);
assert(verification.comparison.passed, 'Python/MATLAB comparison failed.');

% MATLAB에서 생성된 그래프를 화면에 띄웁니다.
openfig(fullfile(outputDir, 'matlab_python_comparison.fig'), 'visible');
