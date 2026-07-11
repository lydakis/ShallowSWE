# %% [markdown]
# # ShallowSWE Kaggle runtime capability probe
#
# This task does not call the model. It records the runtime capabilities required by the canonical
# ShallowSWE repair-loop runner before any funded model execution is attempted.

# %%
from pathlib import Path
import ctypes
import ctypes.util
import errno
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request

import kaggle_benchmarks as kbench
from IPython import get_ipython


def _command(
    *args: str,
    env: dict[str, str] | None = None,
    preexec_fn=None,
) -> dict[str, object]:
    try:
        result = subprocess.run(
            list(args),
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=({**os.environ, **env} if env else None),
            preexec_fn=preexec_fn,
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "output": result.stdout,
    }


def _bwrap_probe() -> dict[str, object]:
    executable = shutil.which("bwrap")
    if executable is None:
        install = _command("apt-get", "update", "-qq")
        if install["ok"]:
            install = _command("apt-get", "install", "-y", "-qq", "bubblewrap")
        executable = shutil.which("bwrap")
        if executable is None:
            return {"installed": False, "ok": False, "install": install}
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        (workspace / "visible.txt").write_text("visible\n")
        result = _command(
            executable,
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--ro-bind",
            "/usr",
            "/usr",
            "--ro-bind-try",
            "/bin",
            "/bin",
            "--ro-bind-try",
            "/lib",
            "/lib",
            "--ro-bind-try",
            "/lib64",
            "/lib64",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--dir",
            "/app",
            "--bind",
            str(workspace),
            "/app",
            "--chdir",
            "/app",
            "bash",
            "-lc",
            "test -f /app/visible.txt && test ! -e /kaggle/input",
        )
    return {"installed": True, **result}


def _outbound_https_probe() -> dict[str, object]:
    try:
        with urllib.request.urlopen("https://example.com", timeout=10) as response:
            return {"ok": True, "status": response.status}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _landlock_abi() -> dict[str, object]:
    # x86_64 Linux syscall number; the live probe records the architecture alongside this result.
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.syscall(444, None, 0, 1)
    if result < 0:
        return {"ok": False, "errno": ctypes.get_errno()}
    return {"ok": True, "abi": result}


def _proot_probe() -> dict[str, object]:
    executable = shutil.which("proot")
    if executable is None:
        install = _command("apt-get", "install", "-y", "-qq", "proot")
        executable = shutil.which("proot")
        if executable is None:
            return {"installed": False, "ok": False, "install": install}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        for directory in ("bin", "lib", "lib64", "usr", "usr/local", "workspace"):
            (root / directory).mkdir(parents=True)
        (root / "workspace" / "visible.txt").write_text("visible\n")
        result = _command(
            executable,
            "-r",
            str(root),
            "-b",
            "/usr:/usr",
            "-b",
            "/usr/local:/usr/local",
            "-b",
            "/bin:/bin",
            "-b",
            "/lib:/lib",
            "-b",
            "/lib64:/lib64",
            "-w",
            "/workspace",
            "/bin/bash",
            "-lc",
            (
                "test -f visible.txt && test ! -e /kaggle/input && "
                "python3 -c 'print(1)' && "
                "! python3 -c 'import socket; socket.socket()'"
            ),
            env={
                "PROOT_NO_SECCOMP": "1",
                "LD_LIBRARY_PATH": (
                    "/usr/local/lib:/usr/lib:/lib:/lib/x86_64-linux-gnu:"
                    "/usr/lib/x86_64-linux-gnu"
                ),
            },
            preexec_fn=_apply_no_network_seccomp,
        )
    return {"installed": True, **result}


def _apply_no_network_seccomp() -> None:
    library = ctypes.util.find_library("seccomp")
    if library is None:
        raise RuntimeError("libseccomp is unavailable")
    seccomp = ctypes.CDLL(library, use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    allow = 0x7FFF0000
    deny = 0x00050000 | errno.EPERM
    context = seccomp.seccomp_init(allow)
    if not context:
        raise OSError(ctypes.get_errno(), "seccomp_init failed")
    try:
        for name in (b"socket", b"socketpair"):
            syscall = seccomp.seccomp_syscall_resolve_name(name)
            if syscall < 0 or seccomp.seccomp_rule_add(context, deny, syscall, 0) != 0:
                raise OSError(ctypes.get_errno(), f"failed to deny {name.decode()}")
        if seccomp.seccomp_load(context) != 0:
            raise OSError(ctypes.get_errno(), "seccomp_load failed")
    finally:
        seccomp.seccomp_release(context)


def _seccomp_probe() -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket; socket.socket(); raise SystemExit('socket unexpectedly allowed')",
        ],
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=_apply_no_network_seccomp,
    )
    return {
        "ok": result.returncode != 0 and "PermissionError" in result.stdout,
        "returncode": result.returncode,
        "output": result.stdout,
    }


def _chroot_seccomp_probe() -> dict[str, object]:
    busybox = shutil.which("busybox")
    if busybox is None:
        install = _command("apt-get", "install", "-y", "-qq", "busybox-static")
        busybox = shutil.which("busybox")
        if busybox is None:
            return {"installed": False, "ok": False, "install": install}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        (root / "bin").mkdir(parents=True)
        (root / "app").mkdir()
        shutil.copy2(busybox, root / "bin" / "busybox")
        (root / "bin" / "sh").symlink_to("busybox")
        (root / "app" / "visible.txt").write_text("visible\n")
        os.chown(root / "app", 65534, 65534)
        os.chown(root / "app" / "visible.txt", 65534, 65534)
        result = subprocess.run(
            [
                "chroot",
                "--userspec=65534:65534",
                str(root),
                "/bin/sh",
                "-c",
                (
                    "cd /app && test -f visible.txt && touch writable.txt && "
                    "test ! -e /kaggle/input && "
                    "! /bin/busybox wget -q -O - https://example.com"
                ),
            ],
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=_apply_no_network_seccomp,
        )
    return {
        "installed": True,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "output": result.stdout,
    }


@kbench.task(
    name="shallowswe-kaggle-environment-probe",
    description="Record Kaggle runtime capabilities required by the ShallowSWE repair-loop runner.",
)
def shallowswe_kaggle_environment_probe(llm) -> bool:
    del llm
    report = {
        "python": sys.version,
        "python_executable": sys.executable,
        "python_ldd": _command("ldd", sys.executable),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "effective_uid": os.geteuid() if hasattr(os, "geteuid") else None,
        "bwrap": _bwrap_probe(),
        "unshare_user": _command("unshare", "--user", "--map-root-user", "true"),
        "unshare_network": _command("unshare", "--net", "true"),
        "outbound_https": _outbound_https_probe(),
        "landlock": _landlock_abi(),
        "libseccomp": ctypes.util.find_library("seccomp"),
        "proot": _proot_probe(),
        "seccomp_no_network": _seccomp_probe(),
        "chroot_seccomp": _chroot_seccomp_probe(),
        "apt_get": shutil.which("apt-get"),
        "paths": {
            "kaggle_input": Path("/kaggle/input").exists(),
            "kaggle_working": Path("/kaggle/working").exists(),
            "proc": Path("/proc").exists(),
        },
    }
    output = Path("/kaggle/working/shallowswe-kaggle-environment-probe.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    kbench.assertions.assert_true(
        True,
        expectation="The ShallowSWE Kaggle runtime capability probe should complete.",
    )
    return True


# %%
SHALLOWSWE_ENVIRONMENT_PROBE_RUN = shallowswe_kaggle_environment_probe.run(
    llm=kbench.llm
)

# %%
get_ipython().run_line_magic("choose", "shallowswe_kaggle_environment_probe")
