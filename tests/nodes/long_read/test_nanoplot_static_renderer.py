"""Keep NanoPlot's native CLI while matching static-export producer/consumer."""

from pathlib import Path
import sys
from types import ModuleType

import pytest

from bionodulo.execution.cache import CacheStore
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.builtin.long_read_family.nanoplot import NanoPlotQCNode


@pytest.mark.parametrize("plot_format", ["png", "svg", "pdf"])
def test_launcher_binds_only_native_static_scope_and_preserves_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plot_format: str,
) -> None:
    bundle = tmp_path / "plotly" / "package_data" / "plotly.min.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text("// installed producer bundle", encoding="utf-8")
    modules = {name: ModuleType(name) for name in (
        "plotly", "kaleido", "kaleido.scopes", "kaleido.scopes.plotly",
        "nanoplotter", "nanoplotter.plot", "nanoplot", "nanoplot.NanoPlot",
    )}
    modules["plotly"].__file__ = str(bundle.parent.parent / "__init__.py")
    calls = []

    def original_scope(**kwargs):
        calls.append(kwargs)
        return kwargs

    modules["kaleido.scopes.plotly"].PlotlyScope = original_scope
    modules["nanoplotter.plot"].PlotlyScope = original_scope
    modules["nanoplotter"].plot = modules["nanoplotter.plot"]
    seen_argv = []

    def native_main():
        seen_argv.extend(sys.argv)
        assert modules["kaleido.scopes.plotly"].PlotlyScope is original_scope
        modules["nanoplotter.plot"].PlotlyScope()
        return 17

    modules["nanoplot.NanoPlot"].main = native_main
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    command = NanoPlotQCNode.render_command({
        "fastq": ["a path/reads.fastq.gz", "literal;$(second).fastq.gz"],
        "output": "output with spaces", "plot_format": plot_format, "threads": 8,
        "min_length": 200, "max_length": 50000, "show_n50": True,
    })
    monkeypatch.setattr(sys, "argv", ["-c", *command[3:]])
    with pytest.raises(SystemExit) as exit_info:
        exec(command[2], {})
    assert exit_info.value.code == 17
    assert seen_argv == ["NanoPlot", *command[3:]]
    assert seen_argv[-3:] == ["--fastq", "a path/reads.fastq.gz", "literal;$(second).fastq.gz"]
    assert calls == [{"plotlyjs": str(bundle.resolve())}]


def test_launcher_refuses_missing_bundle_instead_of_using_legacy_cdn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plotly = ModuleType("plotly")
    plotly.__file__ = str(tmp_path / "plotly" / "__init__.py")
    scope_module = ModuleType("kaleido.scopes.plotly")
    scope_module.PlotlyScope = object
    monkeypatch.setitem(sys.modules, "plotly", plotly)
    monkeypatch.setitem(sys.modules, "kaleido", ModuleType("kaleido"))
    monkeypatch.setitem(sys.modules, "kaleido.scopes", ModuleType("kaleido.scopes"))
    monkeypatch.setitem(sys.modules, "kaleido.scopes.plotly", scope_module)
    command = NanoPlotQCNode.render_command({"fastq": "reads.fastq.gz"})
    with pytest.raises(RuntimeError, match="requires the installed Plotly.js bundle"):
        exec(command[2], {})


def test_renderer_revision_invalidates_existing_blank_plot_cache(tmp_path: Path) -> None:
    blank_report = tmp_path / "NanoPlot-report.html"
    blank_report.write_text("<html>legacy blank plots</html>", encoding="utf-8")
    cache = CacheStore(tmp_path / "cache")
    try:
        arguments = {"node_id": "qc", "node_type": NanoPlotQCNode.NODE_ID,
                     "params": {"plot_format": "png"},
                     "inputs": {"fastq": "same-reads.fastq.gz"}, "upstream_keys": {}}
        legacy = cache.cache_key_for_node(**arguments, tool_version="1.44.1")
        cache.write_marker(legacy, {"qc_report": str(blank_report)})
        assert cache.is_hit(legacy)
        current = cache.cache_key_for_node(
            **arguments, tool_version=WorkflowExecutor._node_cache_version(NanoPlotQCNode),
        )
        assert current != legacy
        assert not cache.is_hit(current)
        assert NanoPlotQCNode.VERSION == "1.44.1"
    finally:
        cache.close()
