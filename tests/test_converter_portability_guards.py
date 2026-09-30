"""Portability regressions: reject conversion that silently changes the graph."""

import json
from pathlib import Path

import pytest

from bionodulo.converter.cwl_converter import export_to_cwl, import_from_cwl
from bionodulo.converter.galaxy_converter import export_to_galaxy, import_from_galaxy
from bionodulo.converter.nextflow_converter import export_to_nextflow, import_from_nextflow
from bionodulo.converter.snakemake_converter import export_to_snakemake, import_from_snakemake


@pytest.mark.parametrize("exporter", [
    export_to_cwl, export_to_galaxy, export_to_nextflow, export_to_snakemake,
])
def test_export_rejects_dangling_executable_edge(exporter) -> None:
    workflow = {
        "nodes": [{"id": "qc", "type": "fastqc", "outputs": {"html": {}}}],
        "edges": [{"id": "broken", "source": "missing", "target": "qc"}],
    }
    with pytest.raises(ValueError, match="unknown executable node"):
        exporter(workflow)


@pytest.mark.parametrize("exporter", [
    export_to_cwl, export_to_galaxy, export_to_nextflow, export_to_snakemake,
])
def test_export_rejects_duplicate_nodes_cycles_and_wrong_ports(exporter) -> None:
    nodes = [
        {"id": "a", "type": "fastqc", "inputs": {"reads": {}}, "outputs": {"report_dir": {}}},
        {"id": "b", "type": "multiqc", "inputs": {"reports": {}},
         "outputs": {"report": {}, "data_dir": {}}},
    ]
    with pytest.raises(ValueError, match="Duplicate workflow node id"):
        exporter({"nodes": [nodes[0], dict(nodes[0])], "edges": []})
    with pytest.raises(ValueError, match="nonempty string id"):
        exporter({"nodes": [None], "edges": []})
    edge = {"id": "e", "source": "a", "target": "b",
            "source_output": "missing", "target_input": "reports"}
    with pytest.raises(ValueError, match="unknown output port"):
        exporter({"nodes": nodes, "edges": [edge]})
    edge["source_output"] = "report_dir"
    edge["target_input"] = "missing"
    with pytest.raises(ValueError, match="unknown input port"):
        exporter({"nodes": nodes, "edges": [edge]})
    edge["target_input"] = "reports"
    reverse = {"id": "reverse", "source": "b", "target": "a",
               "source_output": "report", "target_input": "reads"}
    with pytest.raises(ValueError, match="dependency cycle"):
        exporter({"nodes": nodes, "edges": [edge, reverse]})


@pytest.mark.parametrize("exporter", [export_to_nextflow, export_to_snakemake])
def test_native_qc_exports_reject_unmodeled_widgets_and_quote_special_values(exporter) -> None:
    workflow = {
        "nodes": [{"id": "qc", "type": "fastqc", "inputs": {"reads": {}},
                   "outputs": {"report_dir": {}},
                   "widgets": {"input_path": "sample one.fastq", "threads": 1}},
                  {"id": "summary", "type": "multiqc", "inputs": {"reports": {}},
                   "outputs": {"report": {}, "data_dir": {}},
                   "widgets": {"title": "input sample; $HOME {input}", "filename": "multiqc_report"}}],
        "edges": [{"source": "qc", "target": "summary",
                   "source_output": "report_dir", "target_input": "reports"}],
    }
    exported = exporter(workflow)
    assert "sample one.fastq" in exported
    assert "input sample;" in exported
    if exporter is export_to_nextflow:
        assert exported.count("path input_0, name: 'bionodulo_input/*'") == 2
        assert "\\$HOME" in exported
        assert '"${input_0}"' not in exported
        assert "summary(qc.out.report_dir)" in exported
        assert 'path "data_dir_output", emit: data_dir' in exported
    else:
        assert "{input:q}" in exported
        assert "{{input}}" in exported
        assert "directory('results/qc/report_dir_output')" in exported
        assert "title=lambda wildcards: 'input sample; $HOME {input}'" in exported
    workflow["nodes"][0]["widgets"]["mystery_parameter"] = 10
    with pytest.raises(ValueError, match="cannot preserve widgets"):
        exporter(workflow)


@pytest.mark.parametrize("exporter", [export_to_nextflow, export_to_snakemake])
@pytest.mark.parametrize("force", [None, False, True])
def test_native_multiqc_export_preserves_force_and_isolates_outputs(exporter, force) -> None:
    params = {"filename": "report O'Brien", "title": "QC $HOME {input}"}
    if force is not None:
        params["force"] = force
    workflow = {"nodes": [
        {"id": "summary", "type": "multiqc", "inputs": {"reports": {}},
         "outputs": {"report": {}, "data_dir": {}}, "params": params},
    ], "edges": []}
    exported = exporter(workflow)
    assert ("--force" in exported) is (force is True)
    assert "mktemp -d" in exported
    assert "report_output" in exported and "data_dir_output" in exported
    if exporter is export_to_nextflow:
        assert "path input_0, name: 'bionodulo_input/*'" in exported
        assert '--outdir "\\$multiqc_tmp"' in exported
        assert "--outdir ." not in exported
        assert 'mv -- "\\$multiqc_tmp"/' in exported
        assert "\\$HOME" in exported
    else:
        assert '--outdir "$multiqc_tmp"' in exported
        assert 'mv "$multiqc_tmp"/' in exported
        assert "{{input}}" in exported


@pytest.mark.parametrize("exporter", [export_to_nextflow, export_to_snakemake])
def test_native_multiqc_export_rejects_non_boolean_force(exporter) -> None:
    workflow = {"nodes": [
        {"id": "summary", "type": "multiqc", "inputs": {"reports": {}},
         "outputs": {"report": {}, "data_dir": {}}, "params": {"force": "false"}},
    ], "edges": []}
    with pytest.raises(ValueError, match="force option must be a boolean"):
        exporter(workflow)


def test_nextflow_rejects_unstaged_fastqc_option_files() -> None:
    workflow = {"nodes": [{"id": "qc", "type": "fastqc",
                           "outputs": {"report_dir": {}},
                           "widgets": {"adapters": "adapters.tsv"}}], "edges": []}
    with pytest.raises(ValueError, match="cannot stage"):
        export_to_nextflow(workflow)


def test_snakemake_export_has_no_unprovided_config_and_quotes_python_params() -> None:
    workflow = {
        "nodes": [{"id": "qc", "type": "fastqc", "widgets": {"input_path": "sample one.fastq"},
                   "outputs": {"report_dir": {"path": "results/qc/reports"}}}],
        "edges": [],
    }
    snakefile = export_to_snakemake(workflow)
    assert "configfile:" not in snakefile
    assert "'sample one.fastq'" in snakefile


def test_snakemake_export_writes_only_to_the_requested_destination(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    workflow = {"nodes": [{"id": "qc", "type": "fastqc", "outputs": {"report_dir": {}}}], "edges": []}
    content = export_to_snakemake(workflow)
    assert list(tmp_path.iterdir()) == []
    destination = tmp_path / "generated" / "Snakefile"
    assert export_to_snakemake(workflow, output_path=destination) == content
    assert destination.read_text(encoding="utf-8") == content
    assert set(tmp_path.iterdir()) == {destination.parent}


def test_snakemake_import_skips_all_rule_and_rejects_unhandled_body() -> None:
    parsed = import_from_snakemake('rule all:\n    input:\n        "out.txt"\n'
                                   'rule make:\n    output:\n        "out.txt"\n'
                                   '    shell:\n        "touch out.txt"\n')
    assert [node["id"] for node in parsed["nodes"]] == ["node_make"]
    with pytest.raises(ValueError, match="Unsupported Snakemake rule directive"):
        import_from_snakemake('rule dynamic:\n    run:\n        print("work")\n')


def test_nextflow_import_rejects_unrepresented_processes() -> None:
    script = ('process A {\n  script:\n  """\n  touch a\n  """\n}\n'
              'workflow {\n  B()\n}\n')
    with pytest.raises(ValueError, match="one workflow call"):
        import_from_nextflow(script)


def test_cwl_import_rejects_multiple_sources_instead_of_using_first(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "tool.cwl").write_text(json.dumps({
        "class": "CommandLineTool", "baseCommand": ["cat"], "outputs": {},
    }), encoding="utf-8")
    workflow_path = tmp_path / "workflow.cwl"
    workflow_path.write_text(json.dumps({
        "class": "Workflow", "steps": {"cat": {
            "run": "tools/tool.cwl", "in": {"files": ["a/out", "b/out"]}, "out": [],
        }},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="multiple sources"):
        import_from_cwl(workflow_path)


def test_galaxy_import_rejects_unrepresented_step_type() -> None:
    with pytest.raises(ValueError, match="unsupported Galaxy step type"):
        import_from_galaxy(json.dumps({
            "a_galaxy_workflow": "true", "steps": {"0": {"type": "subworkflow"}},
        }))


def test_cwl_rejects_a_promoted_scalar_instead_of_treating_it_as_a_file() -> None:
    workflow = {"nodes": [{"id": "extract", "type": "extract_columns",
                           "node_info": {"return_names": ["extracted_table"], "input_types": {
                               "required": {"table": {"type": "FILE"}, "columns": {"type": "STRING"}},
                           }}, "ui": {"promotedInputs": ["columns"]}, "params": {}}], "edges": []}
    with pytest.raises(ValueError, match="cannot bind scalar widget"):
        export_to_cwl(workflow)
