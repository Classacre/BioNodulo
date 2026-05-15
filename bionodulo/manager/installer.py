"""Async installation engine for BioNodulo dependencies.

Executes install plans for missing nodes, executables, and Python packages
with progress tracking and cancellation support.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bionodulo.environments.pixi import _to_pixi_env_name
from bionodulo.manager.custom_nodes import install_git, _install_requirements

logger = logging.getLogger(__name__)

EmitCallback = Callable[[str, dict[str, Any]], Any]


@dataclass
class InstallProgress:
    """Progress update for an install job."""

    job_id: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    total_steps: int = 0
    completed_steps: int = 0
    current_step: str = ""
    message: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step,
            "message": self.message,
            "errors": self.errors,
            "percent": (
                int(self.completed_steps / self.total_steps * 100)
                if self.total_steps > 0
                else 0
            ),
        }


class InstallJob:
    """An asynchronous install job with progress tracking."""

    _jobs: dict[str, "InstallJob"] = {}
    _lock = threading.Lock()

    def __init__(self, job_id: str, plan: dict[str, Any], custom_nodes_dir: Path, emit: EmitCallback | None = None):
        self.job_id = job_id
        self.plan = plan
        self.custom_nodes_dir = custom_nodes_dir
        self.progress = InstallProgress(job_id=job_id)
        self._cancelled = False
        self._task: asyncio.Task[Any] | None = None
        self._emit = emit

    @classmethod
    def create(cls, plan: dict[str, Any], custom_nodes_dir: Path, emit: EmitCallback | None = None) -> "InstallJob":
        import uuid

        job_id = f"install_{uuid.uuid4().hex[:8]}"
        job = cls(job_id, plan, custom_nodes_dir, emit=emit)
        with cls._lock:
            cls._jobs[job_id] = job
        return job

    @classmethod
    def get(cls, job_id: str) -> "InstallJob" | None:
        with cls._lock:
            return cls._jobs.get(job_id)

    @classmethod
    def cleanup(cls, job_id: str) -> None:
        with cls._lock:
            cls._jobs.pop(job_id, None)

    def cancel(self) -> None:
        self._cancelled = True
        if self._task and not self._task.done():
            self._task.cancel()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def _send_log(self, level: str, message: str) -> None:
        if self._emit is not None:
            try:
                self._emit(level, {"message": message, "source": "dependency-installer", "job_id": self.job_id})
            except Exception:
                pass

    async def run(self) -> InstallProgress:
        """Execute the install plan asynchronously."""
        self._task = asyncio.current_task()
        self.progress.status = "running"

        missing_nodes = self.plan.get("missing_nodes", [])
        missing_executables = self.plan.get("missing_executables", [])
        missing_packages = self.plan.get("missing_packages", [])
        missing_r_packages = self.plan.get("missing_r_packages", [])
        env_strategy = self.plan.get("env_strategy", "shared")

        self.progress.total_steps = (
            len(missing_nodes) + len(missing_executables) + len(missing_packages) + len(missing_r_packages)
        )

        self._send_log("info", f"Dependency install job started: {self.progress.total_steps} step(s) (strategy: {env_strategy})")

        try:
            # 1. Install missing custom nodes
            for node in missing_nodes:
                if self._cancelled:
                    self.progress.status = "cancelled"
                    self._send_log("warn", "Install job cancelled")
                    return self.progress

                git_url = node.get("git_url", "")
                node_type = node.get("node_type", "unknown")
                if not git_url:
                    err = f"Cannot install {node_type}: no git URL"
                    self.progress.errors.append(err)
                    self._send_log("error", err)
                    self.progress.completed_steps += 1
                    continue

                self.progress.current_step = f"Installing {node_type}"
                self._send_log("info", f"Installing custom node {node_type} from {git_url}...")
                repo_name = Path(git_url).stem
                dest = self.custom_nodes_dir / repo_name

                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(
                    None,
                    lambda: install_git(
                        url=git_url,
                        install_dir=dest,
                        branch=node.get("git_commit", "") or "main",
                        overwrite=True,
                    ),
                )
                if success:
                    self.progress.message = f"Installed {node_type}"
                    self._send_log("success", f"Installed custom node {node_type}")
                else:
                    err = f"Failed to install {node_type} from {git_url}"
                    self.progress.errors.append(err)
                    self._send_log("error", err)
                self.progress.completed_steps += 1

            # 2. Install missing executables via pixi
            # Group by target env when using isolated strategy
            if env_strategy == "isolated" and missing_executables:
                from collections import defaultdict
                env_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for exe in missing_executables:
                    env_name = exe.get("recommended_env", "tools")
                    env_groups[env_name].append(exe)

                for env_name, exes in env_groups.items():
                    if self._cancelled:
                        self.progress.status = "cancelled"
                        self._send_log("warn", "Install job cancelled")
                        return self.progress

                    packages = [e.get("conda_package") or e["name"] for e in exes]
                    self.progress.current_step = f"Installing {len(packages)} package(s) into {env_name}"
                    self._send_log("info", f"Adding packages to pixi env '{env_name}': {', '.join(packages)}...")

                    success = await self._install_pixi_packages(packages, env_name=env_name)
                    if success:
                        self.progress.message = f"Installed into {env_name}"
                        self._send_log("success", f"Installed {len(packages)} package(s) into {env_name}")
                    else:
                        err = f"Failed to install into {env_name}"
                        self.progress.errors.append(err)
                        self._send_log("error", err)
                    self.progress.completed_steps += len(exes)
            else:
                for exe in missing_executables:
                    if self._cancelled:
                        self.progress.status = "cancelled"
                        self._send_log("warn", "Install job cancelled")
                        return self.progress

                    pkg = exe.get("conda_package") or exe["name"]
                    env_name = exe.get("recommended_env", "tools") if env_strategy == "isolated" else "tools"
                    self.progress.current_step = f"Installing {pkg}"
                    self._send_log("info", f"Installing package {pkg} via pixi...")

                    success = await self._install_pixi_package(pkg, env_name=env_name)
                    if success:
                        self.progress.message = f"Installed {pkg}"
                        self._send_log("success", f"Installed package {pkg}")
                    else:
                        err = f"Failed to install {pkg}"
                        self.progress.errors.append(err)
                        self._send_log("error", err)
                    self.progress.completed_steps += 1

            # 3. Install missing Python packages
            for pkg in missing_packages:
                if self._cancelled:
                    self.progress.status = "cancelled"
                    self._send_log("warn", "Install job cancelled")
                    return self.progress

                pkg_name = pkg["name"]
                self.progress.current_step = f"Installing Python package {pkg_name}"
                self._send_log("info", f"Installing Python package {pkg_name} via pixi...")

                success = await self._install_pip_package(pkg_name)
                if success:
                    self.progress.message = f"Installed {pkg_name}"
                    self._send_log("success", f"Installed Python package {pkg_name}")
                else:
                    err = f"Failed to install {pkg_name}"
                    self.progress.errors.append(err)
                    self._send_log("error", err)
                self.progress.completed_steps += 1

            # 4. Install missing R packages
            r_env = "r" if env_strategy == "isolated" else "tools"

            for pkg in missing_r_packages:
                if self._cancelled:
                    self.progress.status = "cancelled"
                    self._send_log("warn", "Install job cancelled")
                    return self.progress

                pkg_name = pkg["name"]
                source = pkg.get("source", "cran")
                self.progress.current_step = f"Installing R package {pkg_name} ({source})"
                self._send_log("info", f"Installing R package {pkg_name} ({source}) into {r_env}...")

                success = await self._install_r_package(pkg_name, source, env_name=r_env)
                if success:
                    self.progress.message = f"Installed {pkg_name}"
                    self._send_log("success", f"Installed R package {pkg_name}")
                else:
                    err = f"Failed to install R package {pkg_name}"
                    self.progress.errors.append(err)
                    self._send_log("error", err)
                self.progress.completed_steps += 1

            self.progress.status = "completed" if not self.progress.errors else "failed"
            if self.progress.errors:
                msg = f"Completed with {len(self.progress.errors)} error(s)"
                self.progress.message = msg
                self._send_log("warn", msg)
            else:
                self.progress.message = "All dependencies installed"
                self._send_log("success", "All dependencies installed")

        except asyncio.CancelledError:
            self.progress.status = "cancelled"
            self._send_log("warn", "Install job cancelled")
            raise
        except Exception as exc:
            logger.exception("Install job failed")
            self.progress.status = "failed"
            self.progress.errors.append(str(exc))
            self._send_log("error", f"Install job failed: {exc}")

        return self.progress

    async def _install_pixi_package(self, package: str, env_name: str = "tools") -> bool:
        """Install a single package via pixi into a specific env."""
        return await self._install_pixi_packages([package], env_name=env_name)

    async def _install_pixi_packages(self, packages: list[str], env_name: str = "tools") -> bool:
        """Install multiple packages via pixi into a specific env.

        Pixi automatically handles the lockfile and environment updates.
        """
        from bionodulo.manager.runtime_installer import get_pixi_path

        pixi = get_pixi_path()
        if pixi is None:
            err = "No pixi executable found"
            logger.error(err)
            self._send_log("error", err)
            return False

        pixi_name = _to_pixi_env_name(env_name)
        pixi_str = str(pixi)
        project_root = Path(__file__).resolve().parent.parent.parent

        # Fast-path: all already installed?
        all_installed = True
        for pkg in packages:
            if not self._is_pixi_package_installed(pixi_str, pixi_name, pkg):
                all_installed = False
                break
        if all_installed:
            self._send_log("info", f"All packages already installed in '{pixi_name}' — skipping")
            return True

        cmd = [pixi_str, "add", "-e", pixi_name] + packages
        self._send_log("info", f"Running: {' '.join(cmd)}")

        last_stderr = ""
        ATTEMPT_TIMEOUT = 300
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []

            async def _drain_stream(stream, chunks, label):
                if stream is None:
                    return
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip()
                    if text:
                        chunks.append(text)
                        if len(chunks) % 5 == 0:
                            self._send_log("info", f"[{label}] {text}")

            await asyncio.wait_for(
                asyncio.gather(
                    _drain_stream(proc.stdout, stdout_chunks, "stdout"),
                    _drain_stream(proc.stderr, stderr_chunks, "stderr"),
                    proc.wait(),
                ),
                timeout=ATTEMPT_TIMEOUT,
            )
            if proc.returncode == 0:
                return True
            last_stderr = "\n".join(stderr_chunks + stdout_chunks)
        except asyncio.TimeoutError:
            self._send_log("warn", f"pixi add timed out after {ATTEMPT_TIMEOUT}s")
            last_stderr = f"pixi add timed out after {ATTEMPT_TIMEOUT}s"
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
        except Exception as exc:
            last_stderr = str(exc)

        err = f"pixi add failed for {packages}: {last_stderr[:800]}"
        logger.error(err)
        self._send_log("error", err)
        return False

    def _is_pixi_package_installed(self, pixi: str, env_name: str, package: str) -> bool:
        """Fast check whether *package* is already in the pixi env."""
        project_root = Path(__file__).resolve().parent.parent.parent
        try:
            result = subprocess.run(
                [pixi, "list", "-e", env_name, "--json"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    for pkg in data:
                        if pkg.get("name", "").lower() == package.lower():
                            return True
        except Exception:
            pass
        return False

    async def _install_pip_package(self, package: str) -> bool:
        """Install a package via pip inside the default pixi environment."""
        from bionodulo.manager.runtime_installer import get_pixi_path

        try:
            pixi = get_pixi_path()
            if pixi is None:
                err = "No pixi found — cannot install pip packages"
                logger.error(err)
                self._send_log("error", err)
                return False

            project_root = Path(__file__).resolve().parent.parent.parent
            cmd = [str(pixi), "run", "-e", "default", "python", "-m", "pip", "install", package]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True
            stderr_text = stderr.decode() if stderr else ""
            err = f"pip install failed for {package}: {stderr_text[:500]}"
            logger.error(err)
            self._send_log("error", err)
            return False
        except Exception as exc:
            err = f"Failed to install {package}: {exc}"
            logger.error(err)
            self._send_log("error", err)
            return False

    async def _install_r_package(self, package: str, source: str = "cran", env_name: str = "tools") -> bool:
        """Install an R package via pixi (conda preferred) or R package manager fallback."""
        from bionodulo.manager.runtime_installer import get_pixi_path

        try:
            pixi = get_pixi_path()
            if pixi is None:
                err = "No pixi found — cannot install R packages"
                logger.error(err)
                self._send_log("error", err)
                return False

            project_root = Path(__file__).resolve().parent.parent.parent
            pixi_name = _to_pixi_env_name(env_name)

            # Map common R packages to conda equivalents for faster, more reliable installs
            CONDA_R_MAP: dict[str, str] = {
                "ggplot2": "r-ggplot2",
                "readr": "r-readr",
                "dplyr": "r-dplyr",
                "tidyr": "r-tidyr",
                "pheatmap": "r-pheatmap",
                "DESeq2": "bioconductor-deseq2",
                "edgeR": "bioconductor-edger",
                "limma": "bioconductor-limma",
                "Biostrings": "bioconductor-biostrings",
                "GenomicRanges": "bioconductor-genomicranges",
                "ape": "r-ape",
                "vegan": "r-vegan",
                "ComplexHeatmap": "bioconductor-complexheatmap",
                "RColorBrewer": "r-rcolorbrewer",
            }

            # Try pixi add first when we have a mapping
            conda_pkg = CONDA_R_MAP.get(package)
            if conda_pkg:
                self._send_log("info", f"Trying pixi add for {package} ({conda_pkg}) into {pixi_name}...")
                conda_cmd = [
                    str(pixi), "add", "-e", pixi_name, conda_pkg,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *conda_cmd,
                    cwd=str(project_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                    if proc.returncode == 0:
                        self._send_log("success", f"Installed {package} via pixi ({conda_pkg})")
                        return True
                    stderr_text = stderr.decode() if stderr else ""
                    self._send_log("warn", f"pixi add failed for {conda_pkg}: {stderr_text[:300]}. Falling back to R package manager...")
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    self._send_log("warn", f"pixi add timed out for {conda_pkg}. Falling back to R package manager...")

            # Fallback: install via R's package manager
            if source.lower() == "bioconductor":
                r_cmd = (
                    f"if (!requireNamespace('BiocManager', quietly=TRUE)) "
                    f"install.packages('BiocManager', repos='https://cloud.r-project.org/'); "
                    f"BiocManager::install('{package}', ask=FALSE)"
                )
            else:
                r_cmd = (
                    f"install.packages('{package}', repos='https://cloud.r-project.org/', "
                    f"dependencies=TRUE)"
                )

            cmd = [str(pixi), "run", "-e", pixi_name, "Rscript", "-e", r_cmd]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                err = f"R install timed out for {package} after 10 minutes"
                logger.error(err)
                self._send_log("error", err)
                return False

            if proc.returncode == 0:
                return True
            stderr_text = stderr.decode() if stderr else ""
            err = f"R install failed for {package}: {stderr_text[:500]}"
            logger.error(err)
            self._send_log("error", err)
            return False
        except Exception as exc:
            err = f"Failed to install R package {package}: {exc}"
            logger.error(err)
            self._send_log("error", err)
            return False
