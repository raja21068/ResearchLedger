"""Docker execution for generated code, and the only place it ever runs.

Generated research code never runs on the host. Two phases: dependency installation is offline unless explicitly opted into
network access; running the experiment never has a network:

  install   network off by default; writes only to a private deps directory
  run       network off, repo mounted read-only, results collected from /out

The image must be digest-pinned (`repo@sha256:<64 hex>`); a tag is a moving target
and is refused. The container gets no host environment, no capabilities, a read-only
root filesystem, and CPU / memory / process limits.
"""
import pathlib
import re
import shutil
import subprocess

DIGEST_PIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*@sha256:[0-9a-f]{64}$")
DEFAULT_IMAGE = "python@sha256:fd76ade0c607f27677bc04be3c60749f400eedc941d9e72967e19a4cedff80c2"


def _safe_mount(path, *, inspect_contents=False):
    """Validate mount sources BEFORE resolve(), which otherwise conceals symlinks."""
    source = pathlib.Path(path).absolute()
    if any(component.is_symlink() for component in (source, *source.parents)):
        raise ValueError(f"unsafe symlink in Docker mount path: {source}")
    if inspect_contents and source.is_dir() and any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError(f"unsafe symlink inside Docker mount: {source}")
    return source.resolve()


def require_digest_pin(image):
    if not image or not DIGEST_PIN.match(str(image)):
        raise ValueError(f"sandbox image {image!r} is not digest-pinned; use repo@sha256:<64 hex>")
    return str(image)


def healthcheck():
    exe = shutil.which("docker")
    if not exe:
        return {"status": "BLOCK", "detail": "docker is not installed",
                "remedy": "install Docker Desktop"}
    done = subprocess.run([exe, "info", "--format", "{{.ServerVersion}}"], capture_output=True,
                          text=True, timeout=30, shell=False)
    if done.returncode != 0:
        return {"status": "BLOCK", "detail": "docker is installed but its daemon is not running",
                "remedy": "start Docker Desktop and wait until it says it is running"}
    return {"status": "PASS", "detail": f"docker {done.stdout.strip()}"}


class Sandbox:
    def __init__(self, image=DEFAULT_IMAGE, cpus=2, memory="4g", pids=512,
                 allow_network_install=False):
        self.image = require_digest_pin(image)
        self.cpus, self.memory, self.pids = cpus, memory, pids
        if not isinstance(allow_network_install, bool):
            raise ValueError("allow_network_install must be a boolean")
        self.allow_network_install = allow_network_install

    def _base(self, network):
        exe = shutil.which("docker")
        if not exe:
            raise ValueError("docker is not installed")
        return [exe, "run", "--rm", "--network", network, "--cpus", str(self.cpus),
                "--memory", self.memory, "--pids-limit", str(self.pids), "--read-only",
                "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=1g"]

    def install(self, repo, deps, timeout=1800):
        """pip-install requirements.txt into `deps` (host dir) with the network on."""
        repo, deps = _safe_mount(repo, inspect_contents=True), _safe_mount(deps)
        deps.mkdir(parents=True, exist_ok=True)
        requirements = repo / "requirements.txt"
        if not requirements.is_file():
            return {"status": "SKIPPED", "detail": "no requirements.txt"}
        command = self._base("bridge" if self.allow_network_install else "none") + [
            "-v", f"{repo}:/workspace:ro", "-v", f"{deps}:/deps:rw", "-w", "/workspace",
            "--env", "PIP_NO_CACHE_DIR=1", "--env", "HOME=/tmp",
            self.image, "python", "-m", "pip", "install", "--no-input",
            *([] if self.allow_network_install else ["--no-index"]),
            "--target", "/deps", "-r", "requirements.txt"]
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, shell=False)
        return {"status": "PASS" if done.returncode == 0 else "FAIL",
                "network": "bridge" if self.allow_network_install else "none",
                "returncode": done.returncode, "stdout": done.stdout[-4000:],
                "stderr": done.stderr[-4000:]}

    def run(self, repo, command, out_dir, deps=None, data=None, timeout=3600):
        """Run `command` in the repo with no network; /out is the only writable mount."""
        repo, out_dir = _safe_mount(repo, inspect_contents=True), _safe_mount(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        mounts = ["-v", f"{repo}:/workspace:ro", "-v", f"{out_dir}:/out:rw", "-w", "/workspace",
                  "--env", "PF_OUT_DIR=/out", "--env", "PYTHONHASHSEED=0",
                  "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "HOME=/tmp"]
        if data is not None:
            safe_data = _safe_mount(data, inspect_contents=True)
            if not safe_data.is_dir():
                raise ValueError(f"dataset mount is not a directory: {safe_data}")
            mounts += ["-v", f"{safe_data}:/data:ro", "--env", "PF_DATA_DIR=/data"]
        if deps and pathlib.Path(deps).is_dir():
            mounts += ["-v", f"{_safe_mount(deps)}:/deps:ro",
                       "--env", "PYTHONPATH=/deps:/workspace"]
        else:
            mounts += ["--env", "PYTHONPATH=/workspace"]
        done = subprocess.run(self._base("none") + mounts + [self.image, *command],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, shell=False)
        return {"status": "PASS" if done.returncode == 0 else "FAIL",
                "returncode": done.returncode, "stdout": done.stdout[-20000:],
                "stderr": done.stderr[-20000:], "image": self.image, "network": "none"}
