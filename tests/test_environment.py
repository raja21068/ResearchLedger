"""Direct unit tests for researchledger/environment.py — mocking
subprocess.run and os.sysconf to exercise branches that depend on hardware
this test machine may not actually have (GPUs, CUDA, POSIX sysconf).
"""

import subprocess

from researchledger.environment import (
    capture_env_vars,
    capture_environment,
    capture_hardware,
    environment_digest,
    git_info,
)


def test_capture_environment_includes_this_package_s_own_dependencies():
    env = capture_environment()
    names = {p.split("==")[0].lower() for p in env["packages"]}
    assert "pyyaml" in names
    assert "jsonschema" in names
    assert env["python_version"]


def test_environment_digest_is_order_independent():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert environment_digest(a) == environment_digest(b)


def test_environment_digest_changes_with_content():
    assert environment_digest({"x": 1}) != environment_digest({"x": 2})


def test_capture_env_vars_only_returns_allowlisted_names(monkeypatch):
    monkeypatch.setenv("RL_TEST_A", "1")
    monkeypatch.setenv("RL_TEST_B", "2")
    result = capture_env_vars(["RL_TEST_A", "RL_TEST_NOT_SET"])
    assert result == {"RL_TEST_A": "1"}


def test_capture_hardware_parses_nvidia_smi_and_nvcc(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd[0] == "nvidia-smi":
            return subprocess.CompletedProcess(cmd, 0, stdout="\nRTX 4090, 550.54.15\n", stderr="")
        if cmd[0] == "nvcc":
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Cuda compilation tools, release 12.4, V12.4.99", stderr=""
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    hardware = capture_hardware()
    assert hardware["gpus"] == ["RTX 4090"]
    assert hardware["gpu_driver_version"] == "550.54.15"
    assert hardware["cuda_version"] == "12.4"


def test_capture_hardware_tolerates_missing_gpu_tools(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    hardware = capture_hardware()
    assert hardware["gpus"] == []
    assert hardware["gpu_driver_version"] is None
    assert hardware["cuda_version"] is None
    assert "cpu_count" in hardware


def test_capture_hardware_uses_sysconf_when_available(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    fake_values = {"SC_PAGE_SIZE": 4096, "SC_PHYS_PAGES": 1000}
    monkeypatch.setattr("os.sysconf", lambda name: fake_values[name], raising=False)
    hardware = capture_hardware()
    assert hardware["total_memory_bytes"] == 4096 * 1000


def test_git_info_outside_a_repository(tmp_path):
    info = git_info(tmp_path)
    assert info == {"commit": None, "dirty": None}


def test_git_info_handles_missing_git_binary(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    info = git_info(tmp_path)
    assert info == {"commit": None, "dirty": None}
