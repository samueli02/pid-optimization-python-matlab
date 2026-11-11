/* The public site runs the same reviewed Python engine in a browser worker.
 * No PID requests or exported results are sent to a remote Python server.
 * Pyodide documentation: https://pyodide.org/en/stable/usage/webworker.html
 */
'use strict';

const PYODIDE_VERSION = '0.29.5';
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
let pyodide;
let activeRequest = null;
let queue = Promise.resolve();
const cancelled = new Set();

function runtime(phase, message, extra = {}) {
  self.postMessage({type: 'runtime', phase, message, ...extra});
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

// The callback receives JSON text, avoiding implicit PyProxy conversion/lifetime.
self.pidProgress = json => {
  if (activeRequest) self.postMessage({type: 'progress', id: activeRequest, progress: JSON.parse(json)});
};

const PYTHON_SETUP = `
import base64, csv, io, json, platform, sys
import numpy as np
import scipy
import sklearn
from scipy.io import savemat
from js import pidProgress
sys.path.insert(0, '/home/pyodide')
from pid_core import DEFAULT_CONFIG, validate_config, simulate, optimize

def _browser_progress(entry):
    pidProgress(json.dumps(entry, allow_nan=False))

def _browser_json_file(name, value):
    return {'name': name, 'mime': 'application/json',
            'text': json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)}

def _browser_csv_file(name, rows, columns):
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError('ML export rows must be a list of objects')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return {'name': name, 'mime': 'text/csv;charset=utf-8', 'text': stream.getvalue()}

def _browser_optimization_files(config, optimization):
    if optimization is None:
        return []
    if not isinstance(optimization, dict):
        raise ValueError('ML export requires an optimization record')
    if not optimization.get('ml_report'):
        return []
    if not isinstance(optimization.get('config'), dict):
        raise ValueError('ML export requires the optimization configuration')
    learned_config = validate_config(optimization['config'])
    if (any(config[key] != learned_config[key] for key in ('plant', 'sim', 'objective'))
            or config['pid']['tf'] != learned_config['pid']['tf']):
        raise ValueError('현재 전달함수·시간 조건·목적함수가 학습 당시와 다릅니다. 다시 ML 최적화를 실행하세요.')
    report = optimization.get('ml_report')
    if not isinstance(report, dict):
        raise ValueError('ML export requires a learning report')
    report = {**report, 'experiment': {
        'trained_best_config': optimization['config'], 'exported_config': config,
        'seed': optimization.get('seed'), 'bounds': optimization.get('bounds'),
        'method': optimization.get('method'),
        'note': '학습 보고서는 최근 최적화 실행 기준이며 python_results.csv는 현재 PID 응답입니다.',
    }}
    return [
        _browser_csv_file('dataset.csv', optimization.get('dataset', []),
            ['iteration', 'kp', 'ki', 'kd', 'cost', 'raw_cost', 'stable', 'spectral_radius',
             'phase', 'split', 'source']),
        _browser_json_file('ml_report.json', report),
        _browser_json_file('optimization_history.json', optimization.get('history', [])),
        _browser_csv_file('surrogate_predictions.csv', optimization.get('surrogate_predictions', []),
            ['kp', 'ki', 'kd', 'actual_log_cost', 'predicted_log_cost', 'predicted_std', 'stable', 'split']),
    ]

def _browser_export(config, optimization=None):
    config = validate_config(config)
    learning_files = _browser_optimization_files(config, optimization)
    response = simulate(config)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['t', 'y', 'u', 'e'])
    writer.writerows(zip(response['t'], response['y'], response['u'], response['e']))
    mat = io.BytesIO()
    savemat(mat, {
        'Kp': config['pid']['kp'], 'Ki': config['pid']['ki'], 'Kd': config['pid']['kd'],
        'Tf': config['pid']['tf'], 'num': np.asarray(config['plant']['num']),
        'den': np.asarray(config['plant']['den']), 'delay': config['plant']['delay'],
        'dt': config['sim']['dt'], 'horizon': config['sim']['horizon'],
        'setpoint': config['sim']['setpoint'], 'objective': config['objective'],
    })
    return {
        'metrics': response['metrics'],
        'files': [
            {'name': 'config.json', 'mime': 'application/json',
             'text': json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False)},
            {'name': 'metrics.json', 'mime': 'application/json',
             'text': json.dumps(response['metrics'], ensure_ascii=False, indent=2, allow_nan=False)},
            {'name': 'python_results.csv', 'mime': 'text/csv;charset=utf-8', 'text': stream.getvalue()},
            {'name': 'pid_parameters.mat', 'mime': 'application/octet-stream',
             'base64': base64.b64encode(mat.getvalue()).decode('ascii')},
        ] + learning_files,
    }

def _browser_dispatch(request_json):
    request = json.loads(request_json)
    action, body = request['action'], request.get('body')
    if action == 'config':
        result = DEFAULT_CONFIG
    elif action == 'simulate':
        result = simulate(body)
    elif action == 'optimize':
        result = optimize(body['config'], bounds=body.get('bounds'),
                          seed=body.get('seed', 42), budget=body.get('budget', 180),
                          progress=_browser_progress)
    elif action == 'export':
        result = _browser_export(body['config'], body.get('optimization'))
    else:
        raise ValueError('Unknown browser action')
    return json.dumps(result, ensure_ascii=False, allow_nan=False)
`;

async function initialize() {
  runtime('loading', 'Python 계산 환경을 내려받는 중입니다. 첫 실행은 잠시 걸릴 수 있습니다.');
  const {loadPyodide} = await import(`${PYODIDE_BASE}pyodide.mjs`);
  pyodide = await loadPyodide({indexURL: PYODIDE_BASE});
  runtime('packages', 'NumPy·SciPy·scikit-learn 계산 및 머신러닝 패키지를 준비하고 있습니다.');
  await pyodide.loadPackage(['numpy', 'scipy', 'scikit-learn']);
  runtime('engine', 'PID 시뮬레이션과 머신러닝 코드를 준비하고 있습니다.');
  const sources = await Promise.all(['pid_core.py', 'pid_ml.py'].map(async name => {
    const response = await fetch(new URL(`./${name}`, self.location.href));
    if (!response.ok) throw new Error(`${name} 다운로드 실패 (${response.status})`);
    return {name, source: await response.text()};
  }));
  for (const {name, source} of sources) {
    pyodide.FS.writeFile(`/home/pyodide/${name}`, source, {encoding: 'utf8'});
  }
  await pyodide.runPythonAsync(PYTHON_SETUP);
  const versions = JSON.parse(pyodide.runPython("json.dumps({'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'scikit-learn': sklearn.__version__})"));
  runtime('ready', '브라우저 Python·머신러닝 엔진 준비 완료', {versions, pyodide: PYODIDE_VERSION});
}

const ready = initialize();
ready.catch(error => runtime('error', 'Python 환경을 불러오지 못했습니다. 네트워크를 확인한 뒤 새로고침해 주세요.', {error: errorMessage(error)}));

self.onmessage = event => {
  const request = event.data;
  if (!request || typeof request !== 'object' || typeof request.id !== 'string') return;
  if (request.type === 'cancel') {
    cancelled.add(request.id);
    return;
  }
  if (request.type !== 'request') return;
  // Pyodide globals are mutable: requests must execute one at a time.
  queue = queue.then(async () => {
    if (cancelled.delete(request.id)) return;
    try {
      await ready;
      if (cancelled.delete(request.id)) return;
      activeRequest = request.id;
      pyodide.globals.set('_pid_request_json', JSON.stringify({action: request.action, body: request.body}));
      // User input is JSON data only. The Python program executed here is fixed.
      const result = await pyodide.runPythonAsync('_browser_dispatch(_pid_request_json)');
      if (!cancelled.has(request.id)) self.postMessage({type: 'result', id: request.id, result: JSON.parse(result)});
    } catch (error) {
      if (!cancelled.has(request.id)) self.postMessage({type: 'error', id: request.id, error: errorMessage(error)});
    } finally {
      activeRequest = null;
      cancelled.delete(request.id);
      if (pyodide) pyodide.globals.delete('_pid_request_json');
    }
  }).catch(error => runtime('error', 'Python 작업 처리 중 오류가 발생했습니다.', {error: errorMessage(error)}));
};
