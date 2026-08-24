"""Governed dual-backend Whisper supervisor with stable-port failover."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(
    os.getenv("TRANSCRIPTION_RUNTIME_ROOT", ROOT / "runtime" / "transcription")
).resolve()
MANIFEST_PATH = RUNTIME / "RUNTIME_MANIFEST.json"
VERSION = "whisper-vulkan-q4_0-rx580-bo1-glossary"
HOST = os.getenv("WHISPER_HOST", "127.0.0.1")
STABLE_PORT = int(os.getenv("WHISPER_PORT", "13312"))
STANDBY_PORT = int(os.getenv("WHISPER_CPU_STANDBY_PORT", "13314"))
HEALTH_TIMEOUT_SECONDS = float(os.getenv("WHISPER_HEALTH_TIMEOUT_SECONDS", "20"))
LEDGER_URL = os.getenv("JARVIS_MEMORYBOARD_URL", "http://127.0.0.1:8001").rstrip("/")
LOCAL_LEDGER = RUNTIME / "ledger" / "backend-selection.jsonl"


class Supervisor:
    def __init__(self) -> None:
        self.stopping = False
        self.gpu: subprocess.Popen[str] | None = None
        self.cpu: subprocess.Popen[str] | None = None
        self.gpu_health_failures = 0
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _validate_artifact(self, relative_path: str, expected_sha256: str) -> None:
        path = RUNTIME / relative_path
        if not path.is_file():
            raise RuntimeError(f"Required transcription artifact is absent: {relative_path}")
        observed = self._sha256(path)
        if observed != expected_sha256:
            raise RuntimeError(
                f"Transcription artifact hash mismatch: {relative_path}"
            )

    def _validate_artifacts(self) -> None:
        vulkan = self.manifest["vulkan"]
        cpu = self.manifest["cpu_fallback"]
        self._validate_artifact(vulkan["binary"], vulkan["binary_sha256"])
        self._validate_artifact(vulkan["model"], vulkan["model_sha256"])
        self._validate_artifact(vulkan["glossary"], vulkan["glossary_sha256"])
        for library in vulkan["shared_libraries"]:
            self._validate_artifact(library["path"], library["sha256"])
        self._validate_artifact(cpu["binary"], cpu["binary_sha256"])
        self._validate_artifact(cpu["model"], cpu["model_sha256"])

    def _binary_env(self) -> dict[str, str]:
        env = os.environ.copy()
        library_dir = RUNTIME / "whisper-vulkan" / "lib"
        prior = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = str(library_dir) + (f":{prior}" if prior else "")
        return env

    def _gpu_command(self) -> list[str]:
        glossary = (
            RUNTIME / "whisper-vulkan" / "glossary.txt"
        ).read_text(encoding="utf-8").strip()
        return [
            str(RUNTIME / "whisper-vulkan" / "bin" / "whisper-server"),
            "-m",
            str(RUNTIME / "whisper-vulkan" / "models" / "ggml-base.en-q4_0.bin"),
            "--host",
            HOST,
            "--port",
            str(STABLE_PORT),
            "-bo",
            "1",
            "--prompt",
            glossary,
        ]

    def _cpu_command(self, port: int) -> list[str]:
        return [
            str(RUNTIME / "whisper-cpu" / "bin" / "whisper-server"),
            "-m",
            str(RUNTIME / "whisper-cpu" / "models" / "ggml-tiny-q8_0.bin"),
            "--host",
            HOST,
            "--port",
            str(port),
            "-ng",
        ]

    @staticmethod
    def _terminate(process: subprocess.Popen[str] | None) -> None:
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    @staticmethod
    def _healthy(port: int, timeout: float = 1.5) -> bool:
        try:
            with urllib_request.urlopen(f"http://{HOST}:{port}/", timeout=timeout) as response:
                return 200 <= response.status < 500
        except (OSError, urllib_error.URLError):
            return False

    def _wait_healthy(self, process: subprocess.Popen[str], port: int) -> bool:
        deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
        while time.monotonic() < deadline and not self.stopping:
            if process.poll() is not None:
                return False
            if self._healthy(port):
                return True
            time.sleep(0.25)
        return False

    def _continuity_link(self, record: dict[str, Any]) -> tuple[str, str | None]:
        payload = {
            "content": (
                f"Transcription runtime {VERSION} selected "
                f"{record['selected_backend']} for {record['event']}."
            ),
            "source_agent": "transcription-runtime-supervisor",
            "session_id": "transcription-runtime",
            "type": "fact",
            "confidence": 1.0,
            "status": "verified",
            "subject": "transcription-runtime-backend-selection",
            "tags": ["jarvis", "transcription", "runtime", record["selected_backend"]],
            "evidence": [
                {
                    "kind": "promotion_certificate",
                    "ref": str(RUNTIME / "ledger" / "PROMOTION_CERTIFICATE.json"),
                    "note": "Validated runtime promotion certificate.",
                },
                {
                    "kind": "runtime_ledger",
                    "ref": str(LOCAL_LEDGER),
                    "note": "Backend selection and failover ledger.",
                },
            ],
        }
        try:
            request = urllib_request.Request(
                LEDGER_URL + "/api/jarvis/memory",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib_request.urlopen(request, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
            memory_id = str((result.get("memory") or {}).get("id") or "").strip()
            return ("linked", memory_id or None)
        except (OSError, ValueError, urllib_error.URLError):
            return ("unavailable", None)

    def _record(self, event: str, selected_backend: str, **details: Any) -> None:
        record: dict[str, Any] = {
            "schema": "jarvis-transcription-runtime-ledger/1.0",
            "timestamp": datetime.now(UTC).isoformat(),
            "runtime_version": VERSION,
            "event": event,
            "selected_backend": selected_backend,
            "stable_endpoint": f"http://{HOST}:{STABLE_PORT}/inference",
            "standby_endpoint": f"http://{HOST}:{STANDBY_PORT}/inference",
            "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
            **details,
        }
        continuity_status, memory_id = self._continuity_link(record)
        record["continuity_ledger"] = {
            "status": continuity_status,
            "memory_id": memory_id,
        }
        LOCAL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LOCAL_LEDGER.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(record, sort_keys=True), flush=True)

    def _start_cpu(self, port: int) -> subprocess.Popen[str]:
        return subprocess.Popen(self._cpu_command(port), text=True)

    def _promote_cpu_fallback(self, reason: str) -> int:
        self._terminate(self.cpu)
        self.cpu = self._start_cpu(STABLE_PORT)
        healthy = self._wait_healthy(self.cpu, STABLE_PORT)
        self._record(
            "backend_failover",
            "cpu",
            reason=reason,
            stable_health=healthy,
            cpu_pid=self.cpu.pid,
        )
        if not healthy:
            return 1
        while not self.stopping and self.cpu.poll() is None:
            time.sleep(1)
        return 0 if self.stopping else int(self.cpu.returncode or 1)

    def run(self) -> int:
        self._validate_artifacts()
        self.cpu = self._start_cpu(STANDBY_PORT)
        cpu_healthy = self._wait_healthy(self.cpu, STANDBY_PORT)
        self.gpu = subprocess.Popen(self._gpu_command(), env=self._binary_env(), text=True)
        gpu_healthy = self._wait_healthy(self.gpu, STABLE_PORT)
        if not gpu_healthy:
            gpu_status = self.gpu.poll()
            self._terminate(self.gpu)
            return self._promote_cpu_fallback(f"gpu_start_failed:{gpu_status}")

        self._record(
            "backend_selected",
            "vulkan",
            stable_health=True,
            standby_health=cpu_healthy,
            gpu_pid=self.gpu.pid,
            cpu_pid=self.cpu.pid,
        )
        while not self.stopping:
            if self.gpu.poll() is not None:
                return self._promote_cpu_fallback(
                    f"gpu_exit:{self.gpu.returncode}"
                )
            if self.cpu.poll() is not None:
                self._record(
                    "standby_restart",
                    "vulkan",
                    reason=f"cpu_exit:{self.cpu.returncode}",
                )
                self.cpu = self._start_cpu(STANDBY_PORT)
                self._wait_healthy(self.cpu, STANDBY_PORT)
            if self._healthy(STABLE_PORT):
                self.gpu_health_failures = 0
            else:
                self.gpu_health_failures += 1
                if self.gpu_health_failures >= 3:
                    self._terminate(self.gpu)
                    return self._promote_cpu_fallback("gpu_health_failed")
            time.sleep(2)
        return 0

    def stop(self, *_args: Any) -> None:
        self.stopping = True
        self._terminate(self.gpu)
        self._terminate(self.cpu)


def main() -> int:
    supervisor = Supervisor()
    signal.signal(signal.SIGTERM, supervisor.stop)
    signal.signal(signal.SIGINT, supervisor.stop)
    try:
        return supervisor.run()
    finally:
        supervisor.stop()


if __name__ == "__main__":
    raise SystemExit(main())
