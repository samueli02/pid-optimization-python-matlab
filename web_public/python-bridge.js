/* API-compatible adapter for the existing PID UI. All state is per visitor. */
(() => {
  'use strict';
  const pending = new Map();
  const jobs = new Map();
  const downloads = new Map();
  let sequence = 0;
  let worker;
  let fatalError = null;
  let resolveReady, rejectReady;
  const ready = new Promise((resolve, reject) => {resolveReady = resolve; rejectReady = reject;});
  ready.catch(() => {}); // initialize() will display a useful error through pidApi.

  function runtime(detail) {
    window.pidRuntimeState = detail;
    window.dispatchEvent(new CustomEvent('pid-runtime-state', {detail}));
  }
  function fail(error) {
    fatalError = error instanceof Error ? error : new Error(String(error));
    rejectReady(fatalError);
    for (const entry of pending.values()) {
      clearTimeout(entry.timer);
      entry.cleanup();
      entry.reject(fatalError);
    }
    pending.clear();
    for (const job of jobs.values()) if (job.status === 'running') {
      job.status = 'error'; job.error = fatalError.message;
    }
    runtime({phase: 'error', message: fatalError.message});
  }

  const initializationTimer = setTimeout(() => {
    worker?.terminate();
    fail(new Error('Python 환경 준비 시간이 초과되었습니다. 네트워크를 확인하고 새로고침해 주세요.'));
  }, 180000);

  try {
    // Use the ESM loader so Python runs off the UI thread without importScripts.
    worker = new Worker(new URL('./pid-worker.js', document.currentScript.src), {type: 'module'});
    worker.onerror = event => {
      clearTimeout(initializationTimer);
      fail(new Error(event.message || 'Python 작업자를 시작할 수 없습니다. 브라우저를 새로고침해 주세요.'));
    };
    worker.onmessage = event => {
      const message = event.data;
      if (message.type === 'runtime') {
        runtime(message);
        if (message.phase === 'ready') {
          clearTimeout(initializationTimer);
          resolveReady(message);
        } else if (message.phase === 'error') {
          clearTimeout(initializationTimer);
          fail(new Error(message.error || message.message));
        }
        return;
      }
      const entry = pending.get(message.id);
      if (!entry) return;
      if (message.type === 'progress') {entry.progress?.(message.progress); return;}
      pending.delete(message.id);
      clearTimeout(entry.timer);
      entry.cleanup();
      if (message.type === 'result') entry.resolve(message.result);
      else entry.reject(new Error(message.error || 'Python 계산에 실패했습니다.'));
    };
  } catch (error) {
    clearTimeout(initializationTimer);
    fail(error);
  }

  const abortError = () => new DOMException('최신 입력으로 계산 요청을 바꿨습니다.', 'AbortError');

  async function rpc(action, body, {signal, progress, timeout = 90000} = {}) {
    if (signal?.aborted) throw abortError();
    await ready;
    if (fatalError) throw fatalError;
    if (signal?.aborted) throw abortError();
    if (pending.size >= 16) throw new Error('계산 요청이 많습니다. 잠시 후 다시 시도해 주세요.');
    const id = `request-${++sequence}`;
    return new Promise((resolve, reject) => {
      const abort = () => {
        const entry = pending.get(id);
        if (!entry) return;
        clearTimeout(entry.timer); pending.delete(id); entry.cleanup();
        worker.postMessage({type: 'cancel', id});
        reject(abortError());
      };
      const cleanup = () => signal?.removeEventListener('abort', abort);
      const timer = setTimeout(() => {
        worker.terminate();
        fail(new Error('계산 시간이 초과되었습니다. 새로고침 후 관측 시간이나 탐색 횟수를 줄여 주세요.'));
      }, timeout);
      pending.set(id, {resolve, reject, progress, timer, cleanup});
      signal?.addEventListener('abort', abort, {once: true});
      worker.postMessage({type: 'request', id, action, body});
    });
  }

  function validateSearch(body) {
    if (!body || typeof body !== 'object' || !body.config) throw new Error('PID 설정이 필요합니다.');
    const budget = body.budget ?? 180, seed = body.seed ?? 42;
    if (!Number.isInteger(budget) || budget < 12 || budget > 1000) throw new Error('탐색 횟수는 12~1000의 정수로 지정하세요.');
    if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) throw new Error('시드는 0~4294967295의 정수로 지정하세요.');
    const bounds = body.bounds ?? [[0,10],[0,5],[0,5]];
    if (!Array.isArray(bounds) || bounds.length !== 3 || bounds.some(b => !Array.isArray(b) || b.length !== 2 || !b.every(Number.isFinite) || b[0] < 0 || b[0] >= b[1] || b[1] > 1000)) throw new Error('PID 탐색 범위를 확인하세요. 0 ≤ 최솟값 < 최댓값 ≤ 1000');
  }

  function revokeDownloads() {
    for (const value of downloads.values()) URL.revokeObjectURL(value.url);
    downloads.clear();
  }
  function exportPayload(body) {
    if (!body || typeof body !== 'object' || !body.config) throw new Error('내보낼 PID 설정이 필요합니다.');
    const payload = {config: body.config};
    if (body.optimization != null) {
      if (typeof body.optimization !== 'object' || Array.isArray(body.optimization)) throw new Error('ML 최적화 기록을 확인할 수 없습니다.');
      // Responses for graphing can be large; exports only need the learning record.
      payload.optimization = {};
      for (const key of ['config', 'dataset', 'ml_report', 'history', 'surrogate_predictions', 'seed', 'bounds', 'method']) {
        if (Object.hasOwn(body.optimization, key)) payload.optimization[key] = body.optimization[key];
      }
    }
    return payload;
  }
  window.pidDownloadUrl = name => {
    const result = downloads.get(name);
    if (!result) throw new Error('먼저 MATLAB 검증 파일 저장을 눌러 주세요.');
    return result.url;
  };

  window.pidApi = async (path, body, signal) => {
    const route = new URL(path, window.location.href);
    if (route.pathname === '/api/config') return rpc('config', undefined, {signal});
    if (route.pathname === '/api/simulate') return rpc('simulate', body, {signal});
    if (route.pathname === '/api/job') {
      const job = jobs.get(route.searchParams.get('id'));
      if (!job) throw new Error('작업을 찾을 수 없습니다.');
      return job;
    }
    if (route.pathname === '/api/optimize') {
      validateSearch(body);
      if ([...jobs.values()].some(j => j.status === 'running')) throw new Error('최적화 작업이 실행 중입니다.');
      await ready;
      if (fatalError) throw fatalError;
      const id = `job-${Date.now()}-${++sequence}`;
      const job = {status: 'running', progress: null};
      jobs.set(id, job);
      // The UI can poll the job while the Python worker calculates.
      rpc('optimize', body, {progress: p => {job.progress = p;}, timeout: 600000})
        .then(result => {job.status = 'done'; job.result = result;})
        .catch(error => {job.status = 'error'; job.error = error.message;});
      while (jobs.size > 8) jobs.delete(jobs.keys().next().value);
      return {job_id: id};
    }
    if (route.pathname === '/api/export') {
      const result = await rpc('export', exportPayload(body), {signal});
      const prepared = [];
      for (const file of result.files) {
        const data = file.base64 === undefined ? file.text : Uint8Array.from(atob(file.base64), c => c.charCodeAt(0));
        prepared.push({name: file.name, blob: new Blob([data], {type: file.mime})});
      }
      revokeDownloads();
      for (const file of prepared) downloads.set(file.name, {url: URL.createObjectURL(file.blob)});
      return {directory: '각 파일을 눌러 내 기기에 다운로드', files: prepared.map(f => f.name), metrics: result.metrics};
    }
    throw new Error('지원하지 않는 요청입니다.');
  };
  window.addEventListener('beforeunload', revokeDownloads);
  runtime({phase: 'loading', message: '브라우저 Python·머신러닝 엔진을 준비하고 있습니다.'});
})();
