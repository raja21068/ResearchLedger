"""Environment and git-state capture for run manifests.

Kept dependency-free (stdlib only) — this runs on every `researchledger run`,
so it must not require anything beyond what the run ledger itself needs.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path


def _package_name(dist) -> str | None:
    return dist.metadata.get("Name")


def capture_environment() -> dict:
    packages = sorted(
        f"{name}=={dist.version}"
        for dist in metadata.distributions()
        for name in (_package_name(dist),)
        if name
    )
    return {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "packages": packages,
    }


def environment_digest(environment: dict) -> str:
    canonical = json.dumps(environment, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def capture_hardware() -> dict:
    cpu_count = os.cpu_count()
    total_memory_bytes = None
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[attr-defined]
        phys_pages = os.sysconf("SC_PHYS_PAGES")  # type: ignore[attr-defined]
        total_memory_bytes = page_size * phys_pages
    except (ValueError, OSError, AttributeError):
        pass  # not available on this platform (e.g. Windows has no os.sysconf)
    gpus: list[str] = []
    driver_version = None
    cuda_version = None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                gpus.append(parts[0])
                if len(parts) > 1 and driver_version is None:
                    driver_version = parts[1]
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        nvcc = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=5)
        if nvcc.returncode == 0:
            match = re.search(r"release (\d+\.\d+)", nvcc.stdout)
            if match:
                cuda_version = match.group(1)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {
        "cpu": platform.processor() or None,
        "cpu_count": cpu_count,
        "total_memory_bytes": total_memory_bytes,
        "gpus": gpus,
        "gpu_driver_version": driver_version,
        "cuda_version": cuda_version,
    }


def capture_env_vars(allowlist: list[str]) -> dict:
    return {name: os.environ[name] for name in allowlist if name in os.environ}


def git_info(cwd: Path) -> dict:
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    if commit is None:
        return {"commit": None, "dirty": None}
    status = run("status", "--porcelain")
    return {"commit": commit, "dirty": bool(status)}
