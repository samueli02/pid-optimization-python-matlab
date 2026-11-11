"""Local, offline PID lab. All simulation and optimization run in Python."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import numpy as np
from scipy.io import savemat
from pid_core import DEFAULT_CONFIG, validate_config, simulate, optimize

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
EXPORT = ROOT / "results" / "latest"
JOBS = {}
JOB_LOCK = threading.Lock()
ALLOWED_EXPORTS = {"config.json", "pid_parameters.mat", "python_results.csv", "metrics.json"}


def export_result(config, directory=EXPORT):
    """Export the exact selected model, numerical settings, gains and response."""
    config = validate_config(config)
    result = simulate(config)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "metrics.json").write_text(json.dumps(result["metrics"], ensure_ascii=False, indent=2), encoding="utf-8")
    with (directory / "python_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["t", "y", "u", "e"])
        writer.writerows(zip(result["t"], result["y"], result["u"], result["e"]))
    savemat(directory / "pid_parameters.mat", {
        "Kp": config["pid"]["kp"], "Ki": config["pid"]["ki"], "Kd": config["pid"]["kd"],
        "Tf": config["pid"]["tf"], "num": np.array(config["plant"]["num"]),
        "den": np.array(config["plant"]["den"]), "delay": config["plant"]["delay"],
        "dt": config["sim"]["dt"], "horizon": config["sim"]["horizon"],
        "setpoint": config["sim"]["setpoint"], "objective": config["objective"],
    })
    return {"directory": str(directory), "files": sorted(ALLOWED_EXPORTS), "metrics": result["metrics"]}


def run_optimization(job_id, config, bounds, seed, budget):
    def report(*args, **kwargs):
        value = args[0] if len(args) == 1 else list(args)
        if kwargs:
            value = kwargs
        with JOB_LOCK:
            JOBS[job_id]["progress"] = value
    try:
        result = optimize(config, bounds=bounds, seed=seed, budget=budget, progress=report)
        with JOB_LOCK:
            JOBS[job_id].update(status="done", result=result)
    except Exception as error:
        with JOB_LOCK:
            JOBS[job_id].update(status="error", error=str(error))


class Handler(BaseHTTPRequestHandler):
    def send_json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        route = urlparse(self.path)
        if route.path == "/api/config":
            return self.send_json(DEFAULT_CONFIG)
        if route.path == "/api/job":
            job_id = parse_qs(route.query).get("id", [""])[0]
            with JOB_LOCK:
                job = dict(JOBS.get(job_id, {}))
            return self.send_json(job or {"error": "작업을 찾을 수 없습니다."}, 200 if job else 404)
        if route.path == "/api/download":
            name = parse_qs(route.query).get("file", [""])[0]
            if name not in ALLOWED_EXPORTS or not (EXPORT / name).is_file():
                return self.send_json({"error": "내보낸 파일이 없습니다."}, 404)
            raw = (EXPORT / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if route.path in ("/", "/index.html"):
            raw = (STATIC / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
            return self.send_json({"error": "외부 사이트의 요청은 허용하지 않습니다."}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1_000_000:
                raise ValueError("요청 크기가 올바르지 않습니다.")
            data = json.loads(self.rfile.read(length))
            route = urlparse(self.path).path
            if route == "/api/simulate":
                return self.send_json(simulate(validate_config(data)))
            if route == "/api/export":
                return self.send_json(export_result(data["config"]))
            if route == "/api/optimize":
                config = validate_config(data["config"])
                bounds = data.get("bounds", [[0, 10], [0, 5], [0, 5]])
                seed = data.get("seed", 42)
                budget = data.get("budget", 180)
                if isinstance(seed, bool) or int(seed) != seed or not 0 <= seed <= 2**32 - 1:
                    raise ValueError("시드는 0~4294967295의 정수로 지정하세요.")
                if isinstance(budget, bool) or int(budget) != budget or not 12 <= budget <= 1000:
                    raise ValueError("탐색 횟수는 12~1000의 정수로 지정하세요.")
                seed, budget = int(seed), int(budget)
                if len(bounds) != 3 or any(len(b) != 2 or not (0 <= float(b[0]) < float(b[1]) <= 1000) for b in bounds):
                    raise ValueError("PID 탐색 범위를 확인하세요. 0 ≤ 최솟값 < 최댓값 ≤ 1000")
                with JOB_LOCK:
                    if any(j["status"] == "running" for j in JOBS.values()):
                        return self.send_json({"error": "최적화 작업이 실행 중입니다."}, 409)
                    job_id = uuid.uuid4().hex
                    JOBS[job_id] = {"status": "running", "progress": None}
                threading.Thread(target=run_optimization, args=(job_id, config, bounds, seed, budget), daemon=True).start()
                return self.send_json({"job_id": job_id}, 202)
            return self.send_json({"error": "알 수 없는 요청입니다."}, 404)
        except (ValueError, KeyError, TypeError) as error:
            return self.send_json({"error": str(error)}, 422)
        except Exception as error:
            return self.send_json({"error": f"계산 실패: {error}"}, 500)


def main():
    parser = argparse.ArgumentParser(description="PID Lab: Python optimization and MATLAB verification")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    address = f"http://127.0.0.1:{args.port}"
    print(f"PID Lab: {address}", flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
