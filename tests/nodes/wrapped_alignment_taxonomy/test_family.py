from __future__ import annotations

import asyncio
import copy
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin import wrapped_alignment_taxonomy as facade
from bionodulo.nodes.builtin._alignment_taxonomy_contracts import (
    NODE_EVIDENCE,
    TOOLS_IUC_GIT_COMMIT,
)


EXPECTED_OUTPUTS = {
    "Add_a_column1": ("out_file1.tsv",),
    "CoverageReport2": ("output1.pdf",),
    "Extract genomic DNA 1": ("output.fasta",),
    "barcode_splitter": ("summary.tsv", "split"),
    "bctools_convert_to_binary_barcode": ("barcodes_ry.fastq",),
    "bctools_extract_alignment_ends": ("alignment_ends.bed",),
    "bctools_extract_barcodes": ("reads_cleaned.fastq", "extracted_barcodes.fastq"),
    "bctools_extract_crosslinked_nucleotides": ("crosslinking_coordinates.bed",),
    "bctools_merge_pcr_duplicates": ("events.bed",),
    "bctools_remove_spurious_events": ("events_filtered.bed",),
    "bctools_remove_tail": ("default.fastq",),
    "blastxml_to_gapped_gff3": ("output.gff3",),
    "bwameth": ("output.bam",),
    "calculate_contrast_threshold": ("threshold_output.txt",),
    "calculate_numeric_param": ("float_param.out", "integer_param.out"),
    "cat_add_names": ("output.tsv",),
    "cat_bins": ("log.txt", "predicted_proteins.faa", "ORF2LCA.tsv", "bin2classification.tsv"),
    "cat_contigs": ("log.txt", "predicted_proteins.faa", "ORF2LCA.tsv", "contig2classification.tsv"),
    "cat_prepare": ("cat_db.txt",),
    "cat_summarise": ("output.tsv",),
    "cawlign": ("output.fasta",),
    "collection_column_join": ("tabular_output.tsv",),
    "collection_element_identifiers": ("output.txt",),
    "compose_text_param": ("out1.out",),
    "compress_file": ("output_file.gz",),
    "crossmap_bam": ("output.sorted.bam",),
    "crossmap_bed": ("output", "output.unmap"),
    "crossmap_bw": ("output.bw",),
    "crossmap_gff": ("output",),
    "crossmap_region": ("output",),
    "crossmap_vcf": ("output", "output.unmap"),
    "crossmap_wig": ("output.bw", "output.sorted.bgr"),
    "som.py": ("results.tsv", "output.metrics.json", "output.stats.csv"),
}

ADAPTER_MODULES = (
    "bionodulo.nodes.builtin._alignment_taxonomy_contracts",
    "bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter",
    "bionodulo.nodes.builtin._alignment_taxonomy_taxonomy_adapter",
    "bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter",
    "bionodulo.nodes.builtin.bctools_family.adapter",
)


def _node_classes() -> dict[str, type[BaseNode]]:
    return {
        candidate.NODE_ID: candidate
        for _name, candidate in inspect.getmembers(facade, inspect.isclass)
        if issubclass(candidate, BaseNode) and candidate is not BaseNode and candidate.NODE_ID
    }


def _owned_node_classes(module: Any) -> list[type[BaseNode]]:
    return [
        candidate
        for _name, candidate in inspect.getmembers(module, inspect.isclass)
        if issubclass(candidate, BaseNode)
        and candidate is not BaseNode
        and candidate.__module__ == module.__name__
        and candidate.NODE_ID
    ]


def _sample_value(name: str, spec: Any) -> Any:
    type_spec = spec[0]
    config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if "default" in config and config["default"] not in ("", []):
        return copy.deepcopy(config["default"])
    if config.get("options"):
        return copy.deepcopy(config["options"][0])
    if isinstance(type_spec, list):
        return copy.deepcopy(type_spec[0])
    if config.get("multiple") or config.get("list") or config.get("is_list") or str(type_spec).endswith("_LIST"):
        return [f"/inputs/{name}.dat"]
    if type_spec == "BOOLEAN":
        return False
    if type_spec == "FLOAT":
        return 1.0
    if type_spec == "INT":
        return 1
    if type_spec in {
        "BAM",
        "BED",
        "BIGWIG",
        "CSV",
        "DIRECTORY",
        "FASTA",
        "FASTQ",
        "FILE",
        "GFA",
        "GFF",
        "GFF_GTF",
        "JSON",
        "NEWICK",
        "STOCKHOLM",
        "TSV",
        "TXT",
        "VCF",
        "ZIP",
    }:
        return f"/inputs/{name}.dat"
    return "value"


def _sample_inputs(node_class: type[BaseNode]) -> dict[str, Any]:
    inputs = {
        name: _sample_value(name, spec)
        for name, spec in node_class.INPUT_TYPES().get("required", {}).items()
    }
    inputs["output"] = f"/work/{node_class.NODE_ID}"
    overrides = {
        "som.py": {"reference_source": "history", "history_item": "/inputs/reference.fa"},
        "bwameth": {"reference_source": "history", "reference": "/inputs/reference.fa"},
        "barcode_splitter": {
            "run_type": "single",
            "snglinput": "/inputs/reads.fastq",
            "idxfiles": ["/inputs/index.fastq"],
        },
        "calculate_numeric_param": {
            "components": [
                {"component_value": 2, "arith": "+"},
                {"component_value": 3, "arith": ""},
            ]
        },
        "compose_text_param": {
            "components": [{"select_param_type": "text", "component_value": "sample"}]
        },
        "collection_column_join": {
            "input_tabular": [
                {"element_identifier": "sample_a", "path": "/inputs/a.tsv"},
                {"element_identifier": "sample_b", "path": "/inputs/b.tsv"},
            ]
        },
        "collection_element_identifiers": {
            "input_collection": [{"element_identifier": "sample_a", "path": "/inputs/a.dat"}]
        },
    }
    inputs.update(overrides.get(node_class.NODE_ID, {}))
    return inputs


def _command_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command)


def _planned_relatives(node_class: type[BaseNode], inputs: dict[str, Any], tmp_path: Path) -> tuple[str, ...]:
    planned = node_class.PLAN_OUTPUTS(inputs, tmp_path)
    paths = planned.values() if isinstance(planned, dict) else planned
    root = tmp_path / node_class.NODE_ID
    return tuple(str(Path(path).relative_to(root)) for path in paths)


def test_exactly_33_stable_ids_have_focused_owners() -> None:
    classes = _node_classes()
    assert set(classes) == set(EXPECTED_OUTPUTS) == set(NODE_EVIDENCE)
    assert len(classes) == 33

    for module_name in ADAPTER_MODULES:
        assert _owned_node_classes(importlib.import_module(module_name)) == []

    for node_id, node_class in classes.items():
        owner = importlib.import_module(node_class.__module__)
        assert _owned_node_classes(owner) == [node_class]
        assert getattr(facade, node_class.__name__) is node_class
        assert node_class.NODE_ID == node_id


@pytest.mark.parametrize("node_id", sorted(EXPECTED_OUTPUTS))
def test_each_contract_validates_and_plans_declared_outputs(node_id: str, tmp_path: Path) -> None:
    node_class = _node_classes()[node_id]
    inputs = _sample_inputs(node_class)

    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert _planned_relatives(node_class, inputs, tmp_path) == EXPECTED_OUTPUTS[node_id]
    if issubclass(node_class, CommandNode):
        command = _command_text(node_class.render_command(inputs))
        assert command
        assert any(executable in command for executable in node_class.REQUIRED_EXECUTABLES)


@pytest.mark.parametrize("node_id", sorted(NODE_EVIDENCE))
def test_each_contract_is_pinned_to_the_exact_wrapper_and_packages(node_id: str) -> None:
    node_class = _node_classes()[node_id]
    evidence = NODE_EVIDENCE[node_id]

    assert node_class.GIT_COMMIT == TOOLS_IUC_GIT_COMMIT == evidence.commit
    assert node_class.GALAXY_WRAPPER_GIT_COMMIT == evidence.commit
    assert node_class.GALAXY_WRAPPER_PATH == evidence.wrapper_path
    assert node_class.GALAXY_WRAPPER_VERSION == evidence.wrapper_version
    assert node_class.VERSION == evidence.wrapper_version
    assert node_class.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert node_class.SOURCE_URL == evidence.source_url
    assert node_class.GALAXY_WRAPPER_SOURCE_URL == evidence.source_url
    assert node_class.DOCUMENTATION_URL
    assert node_class.EXIT_SEMANTICS
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"


@pytest.mark.parametrize(
    ("node_id", "inputs", "error"),
    [
        ("som.py", {"truth": "truth.vcf", "query": "query.vcf", "reference_source": "history"}, "history_item"),
        (
            "bwameth",
            {
                "input_singles": "reads.fastq",
                "reference_source": "history",
                "reference": "reference.fa",
                "single_or_paired_opts": "paired",
                "input_mate1": "reads_1.fastq",
            },
            "input_mate2",
        ),
        ("crossmap_bed", {"input": "regions.bed", "input_chain": "lift.chain", "chromid": "bad"}, "chromid"),
        (
            "Add_a_column1",
            {"input": "table.tsv", "column_types": "str", "add_column_mode": "bad"},
            "add_column_mode",
        ),
        ("calculate_numeric_param", {"components": [{"component_value": 1, "arith": ""}]}, "two components"),
        (
            "compose_text_param",
            {"components": [{"select_param_type": "bad", "component_value": "x"}]},
            "select_param_type",
        ),
        ("barcode_splitter", {"bcfile": "barcodes.tsv", "run_type": "single", "snglinput": "reads.fastq"}, "index read"),
        ("CoverageReport2", {"input1": "reads.bam", "input2": "targets.bed", "threshold": -1}, "threshold"),
        ("bctools_remove_tail", {"reads_fastq": "reads.fastq", "length": -1}, "length"),
        ("blastxml_to_gapped_gff3", {"blastxml": "results.xml", "trim": "bad"}, "trim"),
        (
            "cat_contigs",
            {
                "contigs_fasta": "contigs.fa",
                "database_folder": "/db/cat",
                "taxonomy_folder": "/db/taxonomy",
                "use_previous": "yes",
            },
            "proteins_fasta",
        ),
        ("cawlign", {"fasta": "query.fa", "reference_source": "builtin", "reference_builtin": "bad"}, "reference_builtin"),
    ],
)
def test_conditional_inputs_and_modes_fail_closed(node_id: str, inputs: dict[str, Any], error: str) -> None:
    validation = _node_classes()[node_id].VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert error in str(validation)


def test_expression_nodes_preserve_wrapper_semantics() -> None:
    classes = _node_classes()
    assert asyncio.run(
        classes["calculate_numeric_param"]().run(
            components=[
                {"component_value": 2, "arith": "+"},
                {"component_value": 3, "arith": ""},
            ],
            output_type="integer",
        )
    ) == (5.0, 5)
    assert asyncio.run(
        classes["compose_text_param"]().run(
            components=[
                {"select_param_type": "text", "component_value": "sample_"},
                {"select_param_type": "integer", "component_value": 7},
            ]
        )
    ) == ("sample_7",)
    assert asyncio.run(
        classes["collection_element_identifiers"]().run(
            input_collection=[{"element_identifier": "sample_a"}, {"name": "sample_b"}]
        )
    ) == ("sample_a\nsample_b\n",)


def test_representative_commands_preserve_documented_argument_order() -> None:
    classes = _node_classes()

    assert classes["crossmap_vcf"].render_command(
        {
            "input": "variants.vcf",
            "input_fasta": "target.fa",
            "input_chain": "lift.chain",
            "no_comp_alleles": True,
            "output": "/work/crossmap_vcf",
        }
    ) == (
        "ln -s target.fa /work/crossmap_vcf/genome.fasta && CrossMap vcf lift.chain variants.vcf "
        "/work/crossmap_vcf/genome.fasta --no-comp-alleles /work/crossmap_vcf/output"
    )

    assert classes["Add_a_column1"].render_command(
        {
            "input": "table.tsv",
            "column_types": "str,int,int",
            "expressions": [{"cond": "c3-c2", "add_column_mode": "I", "pos": 2, "new_column_name": "delta"}],
            "header_lines_select": "yes",
            "avoid_scientific_notation": True,
            "output": "/work/column",
        }
    ) == (
        "mkdir -p /work/column && printf '%s\\n' 'c3-c2;2I;delta' > /work/column/expressions.txt && "
        "python column_maker.py --column-types str,int,int --avoid-scientific-notation --header "
        "--file /work/column/expressions.txt --fail-on-non-existent-columns --fail-on-non-computable "
        "table.tsv /work/column/out_file1.tsv"
    )

    assert classes["bctools_merge_pcr_duplicates"].render_command(
        {"alignments_bed": "events.bed", "barcode_library": "barcodes.fastq", "output": "/work/bctools"}
    ) == "merge_pcr_duplicates.py events.bed barcodes.fastq --outfile /work/bctools/events.bed"

    assert classes["cat_add_names"].render_command(
        {
            "input": "classification.tsv",
            "taxonomy_folder": "taxonomy",
            "only_official": False,
            "exclude_scores": True,
            "tabpad_path": "tabpad.py",
            "output": "/work/cat_add_names",
        }
    ) == (
        "CAT add_names -i classification.tsv --taxonomy_folder taxonomy --exclude_scores "
        "-o /work/cat_add_names/output_names.txt && tabpad.py -i /work/cat_add_names/output_names.txt "
        "-o /work/cat_add_names/output.tsv"
    )


def test_source_conflicts_and_implicit_runtime_dependencies_remain_explicit() -> None:
    classes = _node_classes()
    assert classes["som.py"].GALAXY_WRAPPER_VERSION == "0.3.15+galaxy1"
    assert classes["CoverageReport2"].PACKAGE_CONSTRAINTS[3] == "samtools==0.1.18"
    for node_id in ("som.py", "bwameth"):
        assert "samtools" in classes[node_id].REQUIRED_CONDA_PACKAGES
        assert all(not constraint.startswith("samtools==") for constraint in classes[node_id].PACKAGE_CONSTRAINTS)
