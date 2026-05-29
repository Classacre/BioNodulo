"""System hardware stats endpoint for BioNodulo.

Provides CPU, memory, GPU, and VRAM information for the frontend monitor.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import psutil
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_gpu_info() -> list[dict[str, Any]]:
    """Try to detect NVIDIA GPUs via pynvml or nvidia-ml-py."""
    gpus: list[dict[str, Any]] = []
    try:
        import pynvml  # type: ignore[import-untyped]
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = None
            gpus.append(
                {
                    "index": i,
                    "name": name,
                    "type": "cuda",
                    "vram_total": mem_info.total,
                    "vram_used": mem_info.used,
                    "vram_free": mem_info.free,
                    "gpu_utilization": util.gpu,
                    "temperature_c": temp,
                }
            )
        pynvml.nvmlShutdown()
    except ImportError:
        # Try nvidia-ml-py3 fallback
        try:
            from pynvml import nvmlInit, nvmlShutdown, nvmlDeviceGetCount  # type: ignore[import-untyped]
            from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetName  # type: ignore[import-untyped]
            from pynvml import nvmlDeviceGetMemoryInfo, nvmlDeviceGetUtilizationRates  # type: ignore[import-untyped]
            from pynvml import nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU  # type: ignore[import-untyped]
            nvmlInit()
            device_count = nvmlDeviceGetCount()
            for i in range(device_count):
                handle = nvmlDeviceGetHandleByIndex(i)
                name = nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="ignore")
                mem_info = nvmlDeviceGetMemoryInfo(handle)
                util = nvmlDeviceGetUtilizationRates(handle)
                try:
                    temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                except Exception:
                    temp = None
                gpus.append(
                    {
                        "index": i,
                        "name": name,
                        "type": "cuda",
                        "vram_total": mem_info.total,
                        "vram_used": mem_info.used,
                        "vram_free": mem_info.free,
                        "gpu_utilization": util.gpu,
                        "temperature_c": temp,
                    }
                )
            nvmlShutdown()
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("nvidia-ml fallback failed: %s", exc)
    except Exception as exc:
        logger.debug("pynvml GPU detection failed: %s", exc)
    return gpus


def _get_cpu_temp() -> float | None:
    """Try to read CPU temperature via psutil sensors."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        # Look for common sensor names
        for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal"):
            if key in temps:
                entries = temps[key]
                if entries:
                    return entries[0].current
        # Fallback: first available sensor
        for entries in temps.values():
            if entries:
                return entries[0].current
    except Exception as exc:
        logger.debug("CPU temp detection failed: %s", exc)
    return None


@router.get("/system_stats")
async def system_stats() -> dict[str, Any]:
    """Return live hardware statistics."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    cpu_temp = _get_cpu_temp()
    gpus = _get_gpu_info()

    result: dict[str, Any] = {
        "system": {
            "os": sys.platform,
            "python_version": sys.version.split()[0],
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "cpu_percent": cpu_percent,
            "cpu_temp_c": cpu_temp,
            "ram_total": mem.total,
            "ram_used": mem.used,
            "ram_free": mem.available,
            "ram_percent": mem.percent,
        },
        "devices": gpus,
    }
    return result
