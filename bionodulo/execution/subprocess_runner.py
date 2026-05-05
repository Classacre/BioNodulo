from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Awaitable, Callable

LogEmit = Callable[[str, str], Awaitable[None]]


class CommandExecutionError(RuntimeError):
    def __init__(self, command: list[str], returncode: int) -> None:
        super().__init__(f"Command failed with exit code {returncode}: {' '.join(command)}")
        self.command = command
        self.returncode = returncode


async def run_subprocess(command: list[str], *, cwd: Path, stdout_log: Path, stderr_log: Path, emit_log: LogEmit) -> int:
    executable = command[0]
    if shutil.which(executable) is None:
        raise FileNotFoundError(f"Required executable '{executable}' was not found on PATH.")

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def pump(stream: asyncio.StreamReader | None, log_path: Path, stream_name: str) -> None:
        if stream is None:
            return
        with log_path.open("a", encoding="utf-8") as handle:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                handle.write(text + "\n")
                await emit_log(stream_name, text)

    await asyncio.gather(pump(process.stdout, stdout_log, "stdout"), pump(process.stderr, stderr_log, "stderr"))
    return await process.wait()
