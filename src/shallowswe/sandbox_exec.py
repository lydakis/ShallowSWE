from __future__ import annotations

from collections.abc import Sequence
import ctypes
import ctypes.util
import errno
import os
import sys


_SCMP_ACT_ALLOW = 0x7FFF0000
_SCMP_ACT_ERRNO = 0x00050000
_DENIED_SYSCALLS = (
    b"socket",
    b"socketpair",
)


def install_agent_seccomp_filter() -> None:
    """Deny network creation in this process tree before PRoot starts tracing it."""

    libraries = [
        ctypes.util.find_library("seccomp"),
        "libseccomp.so.2",
        "/lib/x86_64-linux-gnu/libseccomp.so.2",
    ]
    seccomp = None
    last_error = None
    for library in libraries:
        if not library:
            continue
        try:
            seccomp = ctypes.CDLL(library, use_errno=True)
            break
        except OSError as exc:
            last_error = exc
    if seccomp is None:
        raise RuntimeError("libseccomp is required for the Kaggle sandbox") from last_error
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
    seccomp.seccomp_rule_add.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]

    context = seccomp.seccomp_init(_SCMP_ACT_ALLOW)
    if not context:
        raise OSError(ctypes.get_errno(), "seccomp_init failed")
    try:
        deny = _SCMP_ACT_ERRNO | errno.EPERM
        for name in _DENIED_SYSCALLS:
            syscall = seccomp.seccomp_syscall_resolve_name(name)
            if syscall >= 0:
                result = seccomp.seccomp_rule_add(context, deny, syscall, 0)
                if result != 0:
                    raise OSError(-result, f"failed to deny {name.decode()}")
        result = seccomp.seccomp_load(context)
        if result != 0:
            raise OSError(-result, "seccomp_load failed")
    finally:
        seccomp.seccomp_release(context)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        raise SystemExit("usage: python -m shallowswe.sandbox_exec -- COMMAND [ARG ...]")
    install_agent_seccomp_filter()
    os.execvp(args[0], args)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
