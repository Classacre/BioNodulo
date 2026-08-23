"""Tests for universal resource auto-scaling."""
import os
from unittest.mock import patch

from bionodulo.execution.executor import WorkflowExecutor


class TestAutoScaleWorkers:
    """_max_parallel_nodes auto-detects vCPUs and respects overrides."""

    def test_env_var_override_wins(self):
        with patch.dict(os.environ, {"BIONODULO_MAX_WORKERS": "16"}):
            executor = WorkflowExecutor.__new__(WorkflowExecutor)
            executor.settings = None
            assert executor._max_parallel_nodes() == 16

    def test_env_var_one_for_serial(self):
        with patch.dict(os.environ, {"BIONODULO_MAX_WORKERS": "1"}):
            executor = WorkflowExecutor.__new__(WorkflowExecutor)
            executor.settings = None
            assert executor._max_parallel_nodes() == 1

    def test_no_env_no_settings_uses_vcpus(self):
        env = {k: v for k, v in os.environ.items() if k != "BIONODULO_MAX_WORKERS"}
        with patch.dict(os.environ, env, clear=True):
            executor = WorkflowExecutor.__new__(WorkflowExecutor)
            executor.settings = None
            detected = executor._detected_vcpus()
            assert executor._max_parallel_nodes() == detected
            assert detected >= 1

    def test_settings_override_used_when_no_env(self):
        env = {k: v for k, v in os.environ.items() if k != "BIONODULO_MAX_WORKERS"}
        with patch.dict(os.environ, env, clear=True):
            executor = WorkflowExecutor.__new__(WorkflowExecutor)
            executor.settings = type("S", (), {"execution": type("E", (), {"max_workers": 8})()})()
            assert executor._max_parallel_nodes() == 8

    def test_detected_vcpus_positive(self):
        executor = WorkflowExecutor.__new__(WorkflowExecutor)
        assert executor._detected_vcpus() >= 1


class TestAutoScaleThreads:
    """_auto_scale_threads bumps threads params to use available cores."""

    def _executor(self):
        ex = WorkflowExecutor.__new__(WorkflowExecutor)
        ex.settings = None
        return ex

    def test_scales_up_low_threads(self):
        ex = self._executor()
        with patch.dict(os.environ, {"BIONODULO_MAX_THREADS": "16"}):
            result = ex._auto_scale_threads({"threads": 4, "other": "value"})
            assert result["threads"] == 16
            assert result["other"] == "value"

    def test_respects_higher_user_setting(self):
        ex = self._executor()
        with patch.dict(os.environ, {"BIONODULO_MAX_THREADS": "8"}):
            result = ex._auto_scale_threads({"threads": 12})
            assert result["threads"] == 12  # not reduced

    def test_no_threads_param_untouched(self):
        ex = self._executor()
        result = ex._auto_scale_threads({"foo": "bar"})
        assert result == {"foo": "bar"}

    def test_invalid_threads_ignored(self):
        ex = self._executor()
        with patch.dict(os.environ, {"BIONODULO_MAX_THREADS": "8"}):
            result = ex._auto_scale_threads({"threads": "not_a_number"})
            assert result["threads"] == "not_a_number"

    def test_threads_at_cap_unchanged(self):
        ex = self._executor()
        with patch.dict(os.environ, {"BIONODULO_MAX_THREADS": "4"}):
            result = ex._auto_scale_threads({"threads": 4})
            assert result["threads"] == 4
