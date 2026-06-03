"""Sandboxed Python code execution node for BioNodulo."""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import sysconfig
from pathlib import Path
from typing import Any

from bionodulo.execution.subprocess_runner import CommandExecutionError, run_subprocess
from bionodulo.nodes.base import BaseNode


MAX_CODE_BYTES = 64 * 1024
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 300


RUNNER_SOURCE = r'''
from __future__ import annotations

import builtins as _builtins
import json as _json
import resource as _resource
import sys as _sys
import traceback as _traceback
from pathlib import Path as _Path

_WORK = _Path("/work").resolve()
_REAL_IMPORT = _builtins.__import__
_REAL_OPEN = _builtins.open
_ALLOWED_IMPORT_ROOTS = {
    "collections",
    "csv",
    "functools",
    "itertools",
    "json",
    "math",
    "numpy",
    "operator",
    "pandas",
    "re",
    "statistics",
}


def _limit_resources() -> None:
    try:
        cpu_seconds = int(_REAL_OPEN(_WORK / "timeout_seconds.txt", encoding="utf-8").read().strip())
    except Exception:
        cpu_seconds = 10
    try:
        _resource.setrlimit(_resource.RLIMIT_CPU, (max(1, cpu_seconds + 1), max(1, cpu_seconds + 1)))
    except Exception:
        pass
    try:
        _resource.setrlimit(_resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    except Exception:
        pass
    try:
        _resource.setrlimit(_resource.RLIMIT_NOFILE, (64, 64))
    except Exception:
        pass


def _is_in_work(path: _Path) -> bool:
    try:
        path.relative_to(_WORK)
        return True
    except ValueError:
        return False


def _safe_open(file, mode="r", *args, **kwargs):
    target = _Path(file)
    if not target.is_absolute():
        target = _WORK / target
    resolved = target.resolve()
    if not _is_in_work(resolved):
        raise PermissionError(f"Python Code can only open files inside {_WORK}")
    if any(flag in str(mode) for flag in ("w", "a", "x", "+")):
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return _REAL_OPEN(resolved, mode, *args, **kwargs)


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0:
        raise ImportError("Relative imports are not allowed in Python Code")
    root = str(name).split(".", 1)[0]
    if root not in _ALLOWED_IMPORT_ROOTS:
        raise ImportError(f"Import of module {root!r} is not allowed in Python Code")
    return _REAL_IMPORT(name, globals, locals, fromlist, level)


def _json_default(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, _Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


_SAFE_BUILTINS = {
    "__build_class__": _builtins.__build_class__,
    "__import__": _safe_import,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "Exception": Exception,
    "False": False,
    "FileNotFoundError": FileNotFoundError,
    "filter": filter,
    "float": float,
    "ImportError": ImportError,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "None": None,
    "object": object,
    "open": _safe_open,
    "PermissionError": PermissionError,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "RuntimeError": RuntimeError,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "True": True,
    "tuple": tuple,
    "type": type,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "zip": zip,
}


def main() -> None:
    _limit_resources()
    inputs = _json.loads(_REAL_OPEN(_WORK / "inputs.json", encoding="utf-8").read())
    code = _REAL_OPEN(_WORK / "user_code.py", encoding="utf-8").read()
    namespace = {
        "__builtins__": _SAFE_BUILTINS,
        "__name__": "__bionodulo_python_code__",
        "inputs": inputs,
        "output": None,
        "result": None,
    }
    try:
        exec(compile(code, str(_WORK / "user_code.py"), "exec"), namespace, namespace)
        value = namespace.get("output")
        if value is None and "result" in namespace:
            value = namespace.get("result")
        with _REAL_OPEN(_WORK / "result.json", "w", encoding="utf-8") as handle:
            _json.dump(value, handle, indent=2, ensure_ascii=True, default=_json_default)
            handle.write("\n")
    except Exception:
        _traceback.print_exc(file=_sys.stderr)
        raise


if __name__ == "__main__":
    main()
'''


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _timeout_label(timeout_seconds: int) -> str:
    unit = "second" if timeout_seconds == 1 else "seconds"
    return f"{timeout_seconds} {unit}"


def _python_runtime() -> tuple[Path, str, list[Path]]:
    base_executable = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    python_root = Path(sys.base_prefix).resolve()
    if not base_executable.exists():
        raise RuntimeError(f"Python executable not found: {base_executable}")
    if not python_root.exists():
        raise RuntimeError(f"Python runtime root not found: {python_root}")

    site_paths: list[Path] = []
    for key in ("purelib", "platlib"):
        path = Path(sysconfig.get_path(key)).resolve()
        if path.exists() and path not in site_paths:
            site_paths.append(path)
    return python_root, base_executable.name, site_paths


def _bwrap_command(bwrap: str, work_dir: Path, timeout_seconds: int) -> list[str]:
    python_root, python_bin, site_paths = _python_runtime()
    command = [
        bwrap,
        "--unshare-user",
        "--uid",
        "0",
        "--gid",
        "0",
        "--unshare-net",
        "--die-with-parent",
        "--clearenv",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--bind",
        str(work_dir),
        "/work",
        "--ro-bind",
        str(python_root),
        "/python",
        "--dir",
        "/usr",
    ]

    for host_path, sandbox_path in (
        (Path("/lib"), "/lib"),
        (Path("/lib64"), "/lib64"),
        (Path("/usr/lib"), "/usr/lib"),
    ):
        if host_path.exists():
            command.extend(["--ro-bind", str(host_path), sandbox_path])

    pythonpath: list[str] = []
    for idx, site_path in enumerate(site_paths):
        sandbox_path = f"/site-packages-{idx}"
        command.extend(["--ro-bind", str(site_path), sandbox_path])
        pythonpath.append(sandbox_path)

    command.extend([
        "--setenv",
        "PATH",
        "/python/bin",
        "--setenv",
        "PYTHONNOUSERSITE",
        "1",
        "--setenv",
        "PYTHONDONTWRITEBYTECODE",
        "1",
        "--setenv",
        "PYTHONPATH",
        ":".join(pythonpath),
        "--chdir",
        "/work",
        f"/python/bin/{python_bin}",
        "/work/runner.py",
    ])
    return command


class PythonCodeNode(BaseNode):
    """Run user Python code in a bubblewrap sandbox."""

    NODE_ID = "python_code"
    DISPLAY_NAME = "Python Code"
    CATEGORY = "data_transform"
    DESCRIPTION = "Run short Python snippets against JSON inputs inside a bubblewrap sandbox."
    SEARCH_ALIASES = ["python", "code", "script", "custom", "numpy", "pandas", "transform"]
    RETURN_TYPES = ("JSON", "ANY", "STRING")
    RETURN_NAMES = ("result_json", "result", "stdout")
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["bwrap"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "code": ("STRING", {
                    "default": 'output = {"received": inputs}',
                    "multiline": True,
                    "description": "Python code. Read JSON data from inputs and assign JSON-serializable output.",
                }),
            },
            "optional": {
                "inputs_json": ("STRING", {
                    "default": "{}",
                    "multiline": True,
                    "description": "JSON object exposed to code as inputs.",
                }),
                "timeout_seconds": ("INT", {
                    "default": 10,
                    "description": "Maximum wall-clock execution time, 1-300 seconds.",
                }),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, Any, str]:
        context = kwargs.pop("context", None)
        code = str(kwargs.get("code", ""))
        if len(code.encode("utf-8")) > MAX_CODE_BYTES:
            raise ValueError(f"Python Code is limited to {MAX_CODE_BYTES} bytes")

        inputs_json = str(kwargs.get("inputs_json", "{}") or "{}")
        try:
            parsed_inputs = json.loads(inputs_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"inputs_json is not valid JSON: {exc.msg}") from exc
        if not isinstance(parsed_inputs, dict):
            raise ValueError("inputs_json must be a JSON object")

        try:
            timeout_seconds = int(kwargs.get("timeout_seconds", 10))
        except (TypeError, ValueError) as exc:
            raise ValueError("timeout_seconds must be an integer") from exc
        if timeout_seconds < MIN_TIMEOUT_SECONDS or timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"timeout_seconds must be between {MIN_TIMEOUT_SECONDS} and {MAX_TIMEOUT_SECONDS}"
            )

        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise RuntimeError("Python Code requires bubblewrap (bwrap) for sandboxed execution")

        out_dir = _node_output_dir(self, context)
        inputs_path = out_dir / "inputs.json"
        code_path = out_dir / "user_code.py"
        runner_path = out_dir / "runner.py"
        timeout_path = out_dir / "timeout_seconds.txt"
        result_path = out_dir / "result.json"

        inputs_path.write_text(json.dumps(parsed_inputs, ensure_ascii=True), encoding="utf-8")
        code_path.write_text(code, encoding="utf-8")
        runner_path.write_text(RUNNER_SOURCE, encoding="utf-8")
        timeout_path.write_text(str(timeout_seconds), encoding="utf-8")
        result_path.unlink(missing_ok=True)

        command = _bwrap_command(bwrap, out_dir, timeout_seconds)
        try:
            completed = await self._run_sandbox_command(context, command, out_dir, timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Python Code timed out after {_timeout_label(timeout_seconds)}") from exc
        except CommandExecutionError as exc:
            stderr = ""
            if exc.stderr_path.exists():
                stderr = exc.stderr_path.read_text(encoding="utf-8", errors="replace").strip()
            message = stderr.splitlines()[-1] if stderr else str(exc)
            raise RuntimeError(f"Python Code failed: {message}") from exc

        if not result_path.exists():
            raise RuntimeError("Python Code did not produce result.json")

        result = json.loads(result_path.read_text(encoding="utf-8"))
        return (str(result_path), result, str(completed.get("stdout", "")))

    async def _run_sandbox_command(
        self,
        context: Any,
        command: list[str],
        out_dir: Path,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        timeout = float(timeout_seconds)
        if context is not None and hasattr(context, "run_command"):
            return await context.run_command(command, cwd=out_dir, timeout=timeout)
        return await run_subprocess(
            command,
            cwd=out_dir,
            stdout_path=out_dir / "stdout.log",
            stderr_path=out_dir / "stderr.log",
            timeout=timeout,
        )
