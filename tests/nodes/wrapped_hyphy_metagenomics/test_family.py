from __future__ import annotations

import copy
import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import wrapped_hyphy_metagenomics as facade
from bionodulo.nodes.builtin.comparative_genomics_family.contracts import (
    AGGRESSIVE,
    EXIT_CODE,
    GALAXY_DEFAULT,
    NODE_EVIDENCE,
    TOOLS_IUC_GIT_COMMIT,
)


HYPHY_IDS = (
    "hyphy_absrel",
    "hyphy_annotate",
    "hyphy_b_still",
    "hyphy_bgm",
    "hyphy_fade",
    "hyphy_fel",
    "hyphy_fubar",
    "hyphy_gard",
    "hyphy_infer_stasis_clusters",
    "hyphy_meme",
    "hyphy_prime",
    "hyphy_relax",
    "hyphy_slac",
    "hyphy_sm19",
    "hyphy_strike_ambigs",
    "hyphy_busted",
    "hyphy_cfel",
    "hyphy_conv",
    "hyphy_cln",
)

EXPECTED_OUTPUTS = {
    "hyphy_absrel": ("absrel_stdout.md", "absrel_output.json"),
    "hyphy_annotate": ("labeled_tree.nhx", "annotate_stdout.md"),
    "hyphy_b_still": ("b_still_output.json", "b_still_stdout.md"),
    "hyphy_bgm": ("bgm_output.json", "bgm_stdout.md"),
    "hyphy_fade": ("fade_output.json", "fade_stdout.md"),
    "hyphy_fel": ("fel_output.json", "fel_stdout.md"),
    "hyphy_fubar": ("fubar_output.json", "fubar_stdout.md"),
    "hyphy_gard": ("gard_output.nex", "gard_output.json", "gard_stdout.md"),
    "hyphy_infer_stasis_clusters": ("output_json.json", "output_log.txt"),
    "hyphy_meme": ("meme_output.json", "meme_stdout.md"),
    "hyphy_prime": ("prime_output.json", "prime_stdout.md"),
    "hyphy_relax": ("relax_output.json", "relax_stdout.md"),
    "hyphy_slac": ("slac_stdout.md", "slac_output.json"),
    "hyphy_sm19": ("sm19_output.json", "sm19_stdout.md"),
    "hyphy_strike_ambigs": ("output.fasta", "strike_ambigs_stdout.md"),
    "hyphy_busted": ("busted_output.json", "busted_stdout.md"),
    "hyphy_cfel": ("cfel_output.json", "cfel_stdout.md"),
    "hyphy_conv": ("proteins.nex",),
    "hyphy_cln": ("cleaned_alignment.fasta",),
    "merge_metaphlan_tables": ("merged_metaphlan_tables.tsv",),
    "extract_metaphlan_database": ("marker_sequences.fasta", "marker_metadata.json"),
    "customize_metaphlan_database": ("custom_marker_sequences.fasta", "custom_marker_metadata.json"),
    "mash_dist": ("distances.tsv",),
    "mash_sketch": ("sketch.msh",),
    "mash_paste": ("sketch.msh",),
    "mash_screen": ("screen.tsv",),
    "mashmap": ("mashmap.out",),
    "fastani": ("fastani.tsv",),
}


def _node_classes() -> dict[str, type[BaseNode]]:
    return {
        candidate.NODE_ID: candidate
        for _name, candidate in inspect.getmembers(facade, inspect.isclass)
        if issubclass(candidate, BaseNode) and candidate is not BaseNode and candidate.NODE_ID
    }


def _sample_value(name: str, spec: Any) -> Any:
    type_spec = spec[0]
    config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if "default" in config and config["default"] not in ("", []):
        return copy.deepcopy(config["default"])
    if config.get("options"):
        return copy.deepcopy(config["options"][0])
    if config.get("multiple") or config.get("list") or str(type_spec).endswith("_LIST"):
        return [f"/inputs/{name}.dat"]
    if type_spec == "BOOLEAN":
        return False
    if type_spec == "FLOAT":
        return 1.0
    if type_spec == "INT":
        return 1
    if type_spec in {
        "ALIGNMENT",
        "DIRECTORY",
        "FASTA",
        "FASTQ",
        "FILE",
        "JSON",
        "PHYLOGENY_TREE",
        "TEXT",
        "TSV",
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
        "hyphy_annotate": {"regexp": "sample.*"},
        "customize_metaphlan_database": {"operation": "keep_markers", "markers": "/inputs/markers.txt"},
    }
    inputs.update(overrides.get(node_class.NODE_ID, {}))
    return inputs


def _command_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command)


def test_facade_exports_exactly_28_stable_ids() -> None:
    classes = _node_classes()
    assert set(classes) == set(EXPECTED_OUTPUTS) == set(NODE_EVIDENCE)
    assert len(classes) == 28
    for node_id, node_class in classes.items():
        assert getattr(facade, node_class.__name__) is node_class
        assert node_class.NODE_ID == node_id


def test_exact_tools_iuc_authorities_and_package_constraints() -> None:
    classes = _node_classes()
    for node_id in HYPHY_IDS:
        evidence = NODE_EVIDENCE[node_id]
        assert evidence.wrapper_path == f"tools/hyphy/{node_id}.xml"
        assert evidence.wrapper_version == "2.5.96+galaxy0"
        expected = (
            ("numpy==1.26.4", "scipy==1.13.1", "python==3.12")
            if node_id == "hyphy_infer_stasis_clusters"
            else ("hyphy==2.5.96",)
        )
        assert evidence.package_constraints == expected
        assert evidence.exit_semantics == EXIT_CODE
        assert evidence.upstream_source_url == "https://github.com/veg/hyphy"
        assert evidence.upstream_ref == "2.5.96"
        assert evidence.upstream_commit == "c2daaafe3f372e8e0f44e275db61f37c74a1516d"

    expected_other = {
        "merge_metaphlan_tables": ("tools/metaphlan/merge_metaphlan_tables.xml", "4.2.4+galaxy0", ("metaphlan==4.2.4",), AGGRESSIVE),
        "extract_metaphlan_database": ("tools/metaphlan/extract_metaphlan_database.xml", "4.2.4+galaxy0", ("metaphlan==4.2.4",), AGGRESSIVE),
        "customize_metaphlan_database": ("tools/metaphlan/customize_metaphlan_database.xml", "4.2.4+galaxy0", ("metaphlan==4.2.4", "seqtk==1.4"), AGGRESSIVE),
        "mash_dist": ("tools/mash/mash_dist.xml", "2.3+galaxy0", ("mash==2.3",), EXIT_CODE),
        "mash_sketch": ("tools/mash/mash_sketch.xml", "2.3+galaxy3", ("mash==2.3",), EXIT_CODE),
        "mash_paste": ("tools/mash/mash_paste.xml", "2.3+galaxy0", ("mash==2.3",), EXIT_CODE),
        "mash_screen": ("tools/mash/mash_screen.xml", "2.3+galaxy4", ("mash==2.3",), EXIT_CODE),
        "mashmap": ("tools/mashmap/mashmap.xml", "3.1.3+galaxy0", ("mashmap==3.1.3",), GALAXY_DEFAULT),
        "fastani": ("tools/fastani/fastani.xml", "1.3", ("fastani==1.3",), EXIT_CODE),
    }
    for node_id, expected in expected_other.items():
        evidence = NODE_EVIDENCE[node_id]
        assert (evidence.wrapper_path, evidence.wrapper_version, evidence.package_constraints, evidence.exit_semantics) == expected

    for node_id, node_class in classes.items():
        evidence = NODE_EVIDENCE[node_id]
        assert node_class.GIT_COMMIT == TOOLS_IUC_GIT_COMMIT
        assert node_class.GALAXY_WRAPPER_PATH == evidence.wrapper_path
        assert node_class.GALAXY_WRAPPER_VERSION == evidence.wrapper_version
        assert node_class.PACKAGE_CONSTRAINTS == evidence.package_constraints
        assert node_class.EXIT_SEMANTICS == evidence.exit_semantics
        assert node_class.SOURCE_URL == evidence.source_url
        assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"

    fastani = NODE_EVIDENCE["fastani"]
    assert fastani.upstream_source_url == "https://github.com/ParBLiSS/FastANI"
    assert fastani.upstream_ref == "v1.3"
    assert fastani.upstream_commit == "6fabd06571fff2a21a08d00292baa6906fddbd7f"


@pytest.mark.parametrize("node_id", sorted(EXPECTED_OUTPUTS))
def test_all_nodes_validate_and_plan_documented_outputs(node_id: str, tmp_path: Path) -> None:
    node_class = _node_classes()[node_id]
    inputs = _sample_inputs(node_class)
    assert node_class.VALIDATE_INPUTS(inputs) is True
    root = tmp_path / node_id
    planned = tuple(str(Path(path).relative_to(root)) for path in node_class.PLAN_OUTPUTS(inputs, tmp_path))
    assert planned == EXPECTED_OUTPUTS[node_id]


@pytest.mark.parametrize(
    ("node_id", "inputs", "expected"),
    [
        ("hyphy_busted", {}, ("busted_output.json", "busted_stdout.md")),
        ("hyphy_busted", {"save_alternative_model": True}, ("busted_output.json", "busted_stdout.md", "alternative_model.nhx")),
        ("hyphy_prime", {}, ("prime_output.json", "prime_stdout.md")),
        ("hyphy_prime", {"save_intermediate": True}, ("prime_output.json", "prime_stdout.md", "intermediate_fits.json")),
        ("fastani", {}, ("fastani.tsv",)),
        ("fastani", {"matrix": True}, ("fastani.tsv", "fastani.tsv.matrix")),
        ("fastani", {"visualize": True}, ("fastani.tsv", "fastani.tsv.visual")),
        ("fastani", {"matrix": True, "visualize": True}, ("fastani.tsv", "fastani.tsv.matrix", "fastani.tsv.visual")),
    ],
)
def test_conditional_output_ports_are_explicit(
    node_id: str,
    inputs: dict[str, Any],
    expected: tuple[str, ...],
    tmp_path: Path,
) -> None:
    node_class = _node_classes()[node_id]
    planned = tuple(Path(path).name for path in node_class.PLAN_OUTPUTS(inputs, tmp_path))
    assert planned == expected


@pytest.mark.parametrize(
    ("node_id", "inputs", "message"),
    [
        ("hyphy_absrel", {"input_file": "/in.fa", "branch_sel": "specify"}, "branch label"),
        ("hyphy_annotate", {"input_tree": "/tree.nhx", "selection_method": "regexp"}, "regular expression"),
        ("merge_metaphlan_tables", {"abundance_tables": []}, "At least one"),
        ("extract_metaphlan_database", {"database_path": "", "database_key": "db"}, "directory"),
        ("customize_metaphlan_database", {"marker_sequences": "/m.fa", "marker_metadata": "/m.json"}, "new_marker_sequences"),
        ("mash_dist", {"reference": "/ref.msh", "query": "", "threads": 1}, "query"),
        ("mash_sketch", {"reads_assembly_selector": "assembly", "assembly": ""}, "assembly input"),
        ("mash_paste", {"msh_files": []}, "At least one"),
        ("mash_screen", {"queries": "/q.msh", "pool_input_selector": "paired", "pool_1": "/r1.fq"}, "all read inputs"),
        ("mashmap", {"query": [], "reflist": ["/ref.fa"]}, "query"),
        ("fastani", {"query": [], "reference": ["/ref.fa"]}, "query genome"),
    ],
)
def test_conditional_contracts_fail_closed(node_id: str, inputs: dict[str, Any], message: str) -> None:
    result = _node_classes()[node_id].VALIDATE_INPUTS(inputs)
    assert isinstance(result, str)
    assert message in result


@pytest.mark.parametrize(
    ("node_id", "inputs", "ordered_fragments"),
    [
        (
            "hyphy_absrel",
            {"input_file": "/in.fa", "output": "/work/absrel"},
            ("hyphy CPU=4 absrel", "--alignment ./input.fasta", "--output /work/absrel/absrel_output.json"),
        ),
        (
            "merge_metaphlan_tables",
            {"abundance_tables": ["/a.tsv", "/b.tsv"], "element_identifiers": ["a", "b"], "output": "/work/merge"},
            ("ln -s /a.tsv a", "ln -s /b.tsv b", "merge_metaphlan_tables.py a b"),
        ),
        (
            "mash_sketch",
            {"reads_assembly_selector": "assembly", "assembly": "/contigs.fa", "output": "/work/sketch"},
            ("ln -sf /contigs.fa contigs.fa", "mash sketch", "-o /work/sketch/sketch"),
        ),
        (
            "mashmap",
            {"query": ["/q.fa"], "reflist": ["/r.fa"], "output": "/work/mashmap"},
            ("mashmap", "--perc_identity 85.0", "-r /r.fa", "-q /q.fa", "> /work/mashmap/mashmap.out"),
        ),
        (
            "fastani",
            {"query": ["/q.fa"], "reference": ["/r.fa"], "matrix": True, "output": "/work/fastani"},
            ("fastANI", "-q /q.fa", "-r /r.fa", "-o /work/fastani/fastani.tsv", "--matrix"),
        ),
    ],
)
def test_representative_argv_ordering(
    node_id: str,
    inputs: dict[str, Any],
    ordered_fragments: tuple[str, ...],
) -> None:
    command = _command_text(_node_classes()[node_id].render_command(inputs))
    positions = [command.index(fragment) for fragment in ordered_fragments]
    assert positions == sorted(positions)
