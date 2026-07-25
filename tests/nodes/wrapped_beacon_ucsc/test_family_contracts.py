from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin import wrapped_beacon_ucsc_family as family
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family import (
    Beacon2ImportNode,
    Beacon2Vcf2BffNode,
    FaSplitNode,
    GffCompareNode,
    GffReadNode,
    UcscAxtChainNode,
    UcscMafAddIRowsNode,
    UcscMafCoverageNode,
    UcscMafFetchNode,
    UcscMafFragNode,
    UcscMafFragsNode,
    UcscMafGeneNode,
    UcscNetFilterNode,
    UcscWigToBigWigNode,
)
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    ASSET_SHA256,
    BEACON2_RI_GIT_COMMIT,
    BIONET_GIT_COMMIT,
    GFFCOMPARE_GIT_COMMIT,
    GFFREAD_GIT_COMMIT,
    HEINZ_GIT_COMMIT,
    KENT_357_GIT_COMMIT,
    KENT_482_GIT_COMMIT,
    KENT_490_GIT_COMMIT,
    PUBLIC_UCSC_DB_CONFIG,
    QQMAN_GIT_COMMIT,
    TOOLS_IUC_GIT_COMMIT,
    asset_path,
)


EXPECTED_IDS = {
    "beacon2_import",
    "beacon2_csv2xlsx",
    "beacon2_pxf2bff",
    "beacon2_vcf2bff",
    "qq_manhattan",
    "heinz_visualization",
    "heinz",
    "heinz_scoring",
    "heinz_bum",
    "brew3r_r",
    "ucsc_chainswap",
    "ucsc_chainsort",
    "ucsc_netsyntenic",
    "ucsc_netchainsubset",
    "ucsc_netfilter",
    "ucsc_chainprenet",
    "ucsc_nettoaxt",
    "ucsc-twobittofa",
    "ucsc_wigtobigwig",
    "ucsc_axtomaf",
    "ucsc_axtchain",
    "ucsc_chainnet",
    "fasplit",
    "fatovcf",
    "ucsc_maffilter",
    "ucsc_maffetch",
    "ucsc_mafaddirows",
    "ucsc_maffrag",
    "ucsc_maffrags",
    "ucsc_mafgene",
    "gtftobed12",
    "gffread",
    "gffcompare",
    "ucsc_mafcoverage",
    "maftoaxt",
    "ucsc_chainantirepeat",
}

ALL_NODE_CLASSES = tuple(getattr(family, name) for name in family.__all__)

SPECIAL_RUNTIME_COMMITS = {
    "beacon2_import": TOOLS_IUC_GIT_COMMIT,
    "beacon2_csv2xlsx": BEACON2_RI_GIT_COMMIT,
    "beacon2_pxf2bff": BEACON2_RI_GIT_COMMIT,
    "beacon2_vcf2bff": BEACON2_RI_GIT_COMMIT,
    "qq_manhattan": QQMAN_GIT_COMMIT,
    "heinz_visualization": TOOLS_IUC_GIT_COMMIT,
    "heinz": HEINZ_GIT_COMMIT,
    "heinz_scoring": TOOLS_IUC_GIT_COMMIT,
    "heinz_bum": BIONET_GIT_COMMIT,
    "brew3r_r": TOOLS_IUC_GIT_COMMIT,
    "gtftobed12": KENT_357_GIT_COMMIT,
    "gffread": GFFREAD_GIT_COMMIT,
    "gffcompare": GFFCOMPARE_GIT_COMMIT,
    "ucsc_mafgene": KENT_490_GIT_COMMIT,
}

PATH_TYPES = {
    "BAM",
    "BED",
    "CSV",
    "DIRECTORY",
    "FASTA",
    "FILE",
    "GFF_GTF",
    "GTF",
    "JSON",
    "TSV",
    "TXT",
    "VCF",
}

MINIMAL_OVERRIDES: dict[str, dict[str, Any]] = {
    "beacon2_import": {
        "db_auth_source": "admin",
        "db_user": "beacon-user",
        "db_password": "secret",
    },
    "heinz_scoring": {"input_bum": "/inputs/bum.txt"},
    "ucsc_axtomaf": {
        "in_tar_ref_index": "/inputs/target.sizes",
        "in_que_ref_index": "/inputs/query.sizes",
    },
    "ucsc_chainnet": {
        "in_tar_ref_index": "/inputs/target.sizes",
        "in_que_ref_index": "/inputs/query.sizes",
    },
    "ucsc_chainprenet": {
        "in_tar_ref_index": "/inputs/target.sizes",
        "in_que_ref_index": "/inputs/query.sizes",
    },
    "ucsc_maffrag": {"start": 1, "end": 2},
    "ucsc_wigtobigwig": {"index_len_path": "/inputs/chrom.sizes"},
}


def _minimal_inputs(node_class: type, output: Path) -> dict[str, Any]:
    inputs: dict[str, Any] = {"output": str(output)}
    for name, spec in node_class.INPUT_TYPES().get("required", {}).items():
        type_name, metadata = spec
        if "default" in metadata:
            value: Any = metadata["default"]
        elif metadata.get("options"):
            value = metadata["options"][0]
        elif metadata.get("multiple"):
            value = [f"/inputs/{name}.dat"]
        elif type_name == "INT":
            value = 1
        elif type_name == "FLOAT":
            value = 0.5
        elif type_name in PATH_TYPES:
            value = f"/inputs/{name}.dat"
        else:
            value = "value"
        inputs[name] = value
    inputs.update(MINIMAL_OVERRIDES.get(node_class.NODE_ID, {}))
    return inputs


def test_family_exports_exactly_the_36_stable_ids() -> None:
    assert len(ALL_NODE_CLASSES) == 36
    assert {node_class.NODE_ID for node_class in ALL_NODE_CLASSES} == EXPECTED_IDS


@pytest.mark.parametrize("node_class", ALL_NODE_CLASSES, ids=lambda node_class: node_class.NODE_ID)
def test_every_node_has_pinned_wrapper_and_runtime_evidence(node_class: type) -> None:
    expected_runtime_commit = SPECIAL_RUNTIME_COMMITS.get(node_class.NODE_ID, KENT_482_GIT_COMMIT)
    assert node_class.GIT_COMMIT == expected_runtime_commit
    assert node_class.GALAXY_WRAPPER_GIT_COMMIT == TOOLS_IUC_GIT_COMMIT
    assert node_class.RUNTIME_VERSION
    assert node_class.PACKAGE_CONSTRAINT
    assert node_class.REQUIRED_EXECUTABLES
    assert node_class.RETURN_NAMES


@pytest.mark.parametrize("node_class", ALL_NODE_CLASSES, ids=lambda node_class: node_class.NODE_ID)
def test_minimal_valid_contract_renders_and_plans_outputs(node_class: type, tmp_path: Path) -> None:
    inputs = _minimal_inputs(node_class, tmp_path / node_class.NODE_ID)
    assert node_class.VALIDATE_INPUTS(inputs) is True
    command = node_class.render_command(inputs)
    assert command
    assert node_class.REQUIRED_EXECUTABLES[0] in command
    assert node_class.PLAN_OUTPUTS(inputs, tmp_path)


@pytest.mark.parametrize("name,expected", sorted(ASSET_SHA256.items()))
def test_vendored_galaxy_assets_match_the_pinned_tools_iuc_bytes(name: str, expected: str) -> None:
    assert hashlib.sha256(Path(asset_path(name)).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize(
    "node_class,inputs,asset_name",
    [
        (family.QQManhattanNode, {"data": "gwas.tsv"}, "manhattan.R"),
        (family.HeinzVisualizationNode, {"subnetwork": "network.txt"}, "heinz_visualization.py"),
        (
            family.HeinzScoringNode,
            {"node": "nodes.tsv", "input_bum": "bum.txt"},
            "heinz_scoring.py",
        ),
        (family.HeinzBumNode, {"p_values": "pvalues.txt"}, "heinz_bum.R"),
        (
            family.Brew3rRNode,
            {"gtf_to_extend": "base.gtf", "gtf_to_overlap": "new.gtf"},
            "brew3r.r_script.R",
        ),
    ],
)
def test_helper_script_nodes_use_the_vendored_asset_by_default(
    node_class: type,
    inputs: dict[str, Any],
    asset_name: str,
) -> None:
    assert asset_path(asset_name) in node_class.render_command({**inputs, "output": "/work/node"})


def test_beacon_import_requires_secret_credentials_and_removes_the_temporary_config() -> None:
    base = {"input_json_file": "input.json", "database": "beacon", "collection": "variants"}
    assert "configured credential" in str(Beacon2ImportNode.VALIDATE_INPUTS(base))
    inputs = {
        **base,
        "db_auth_source": "admin",
        "db_user": "user",
        "db_password": "secret",
        "output": "/work/beacon2_import",
    }
    command = Beacon2ImportNode.render_command(inputs)
    assert "umask 077" in command
    assert "trap 'rm -f /work/beacon2_import/.beacon2_db_auth.json' EXIT" in command
    assert "example" not in command
    password_metadata = Beacon2ImportNode.INPUT_TYPES()["optional"]["db_password"][1]
    assert password_metadata["password"] is True


def test_beacon_vcf_contract_runs_in_cwd_and_only_promises_bff() -> None:
    valid = {"input": "variants.vcf.gz", "dataset_id": "dataset", "genome": "hg38"}
    assert Beacon2Vcf2BffNode.VALIDATE_INPUTS(valid) is True
    assert "dataset_id is required" in str(
        Beacon2Vcf2BffNode.VALIDATE_INPUTS({"input": "variants.vcf.gz", "genome": "hg38"})
    )
    assert "must be bff" in str(Beacon2Vcf2BffNode.VALIDATE_INPUTS({**valid, "format": "hash"}))
    command = Beacon2Vcf2BffNode.render_command({**valid, "output": "/work/vcf2bff"})
    assert "--format bff --project-dir ." in command
    assert "canonicalize_vcf2bff.py" in command
    assert "gunzip" not in command
    assert Beacon2Vcf2BffNode.RUN_IN_NODE_OUTPUT_DIR is True


def test_vcf2bff_canonicalizer_removes_runtime_identity_and_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "records.json.gz"
    record = {
        "variantInternalId": "chr1_1_A_C",
        "_info": {
            "datasetId": "dataset",
            "genome": "hg38",
            "vcf2bff": {
                "version": "2.0.0",
                "hostname": "worker-123",
                "user": "runner",
                "cwd": "/tmp/random",
                "ncpuhost": 8,
            },
        },
    }
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    outputs = [tmp_path / "first.json", tmp_path / "second.json"]
    for output in outputs:
        subprocess.run(
            [sys.executable, asset_path("canonicalize_vcf2bff.py"), str(source), str(output)],
            check=True,
        )
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    normalized = json.loads(outputs[0].read_text().strip())
    assert normalized["_info"]["vcf2bff"] == {"version": "2.0.0"}


@pytest.mark.parametrize(
    "node_class,inputs",
    [
        (UcscMafFetchNode, {"bed_file": "regions.bed", "genome": "hg38", "track": "multiz100way"}),
        (
            UcscMafFragNode,
            {"genome": "hg38", "track": "multiz100way", "chrom": "chr1", "start": 1, "end": 2, "strand": "."},
        ),
        (UcscMafFragsNode, {"bed_file": "regions.bed", "genome": "hg38", "track": "multiz100way"}),
        (UcscMafCoverageNode, {"maf_file": "input.maf", "genome": "hg38"}),
        (
            UcscMafGeneNode,
            {
                "twoBitFile": "genome.2bit",
                "db_name": "hg38",
                "maf_file": "alignment.bin",
                "genepred_file": "genes.tab",
                "species_list": "species.txt",
            },
        ),
    ],
    ids=lambda value: value.NODE_ID if isinstance(value, type) else None,
)
def test_database_backed_ucsc_nodes_use_an_isolated_home_and_pinned_default_config(
    node_class: type,
    inputs: dict[str, Any],
) -> None:
    command = node_class.render_command({**inputs, "output": f"/work/{node_class.NODE_ID}"})
    assert str(PUBLIC_UCSC_DB_CONFIG) in command
    assert "ucsc-home/.hg.conf" in command
    assert "HOME=" in command
    assert "ucsc_db_connection.conf" not in command.replace(str(PUBLIC_UCSC_DB_CONFIG), "")


def test_maffrag_precreates_an_empty_valid_artifact_for_no_alignment_results() -> None:
    command = UcscMafFragNode.render_command(
        {
            "genome": "hg38",
            "track": "multiz100way",
            "chrom": "chr1",
            "start": 1,
            "end": 2,
            "strand": ".",
            "output": "/work/ucsc_maffrag",
        }
    )
    assert command.startswith("touch /work/ucsc_maffrag/out.maf && ")


def test_maf_add_irows_requires_logical_species_bed_names() -> None:
    base = {"input_maf": "input.maf", "twoBitFile": "genome.2bit", "nBeds": ["/cloud/a", "/cloud/b"]}
    assert "one logical species filename" in str(UcscMafAddIRowsNode.VALIDATE_INPUTS(base))
    inputs = {
        **base,
        "nBed_element_identifiers": ["gorGor3.bed", "hg38.bed"],
        "output": "/work/ucsc_mafaddirows",
    }
    assert UcscMafAddIRowsNode.VALIDATE_INPUTS(inputs) is True
    command = UcscMafAddIRowsNode.render_command(inputs)
    assert "/work/ucsc_mafaddirows/gorGor3.bed" in command
    assert "echo gorGor3.bed >> /work/ucsc_mafaddirows/bed.txt" in command
    assert "-nBeds=/work/ucsc_mafaddirows/bed.txt" in command


def test_mafgene_preserves_bigmaf_and_genepred_file_semantics() -> None:
    inputs = {
        "twoBitFile": "genome.2bit",
        "db_name": "hg38",
        "maf_file": "/cloud/alignment",
        "maf_format": "bigMaf",
        "genepred_file": "/cloud/genes",
        "species_list": "species.txt",
        "output": "/work/ucsc_mafgene",
    }
    command = UcscMafGeneNode.render_command(inputs)
    assert "/work/ucsc_mafgene/input.bigMaf" in command
    assert "/work/ucsc_mafgene/input.gp" in command
    assert "-useFile" in command
    assert UcscMafGeneNode.INPUT_TYPES()["required"]["species_list"][0] == "FILE"
    assert UcscMafGeneNode.INPUT_TYPES()["optional"]["gene_list"][0] == "FILE"
    assert "maf_format must be one of" in str(UcscMafGeneNode.VALIDATE_INPUTS({**inputs, "maf_format": "maf"}))


@pytest.mark.parametrize("split_type,expected", [("sequence", " 10 "), ("size", " 100 ")])
def test_fasplit_uses_mode_specific_count_defaults(split_type: str, expected: str) -> None:
    command = FaSplitNode.render_command(
        {"input": "input.fa", "split_type": split_type, "output": "/work/fasplit"}
    )
    assert expected in command


def test_fasplit_maps_the_optional_lift_file_to_a_stable_port(tmp_path: Path) -> None:
    inputs = {"input": "input.fa", "split_type": "size", "lift": True}
    planned = FaSplitNode.PLAN_OUTPUTS(inputs, tmp_path)
    assert [path.name for path in planned] == ["output_list", "fasplit.lft"]
    assert FaSplitNode.MAP_PLANNED_OUTPUTS(planned) == {
        "output_list": planned[0],
        "lift_file": planned[1],
    }


def test_gffread_fasta_only_mode_does_not_plan_a_nonexistent_annotation(tmp_path: Path) -> None:
    inputs = {
        "input": "features.gtf",
        "gff_fmt": "none",
        "reference_genome_source": "history",
        "genome_fasta": "genome.fa",
        "fa_outputs": ["exons"],
        "output": "/work/gffread",
    }
    command = GffReadNode.render_command(inputs)
    planned = GffReadNode.PLAN_OUTPUTS(inputs, tmp_path)
    assert "-w /work/gffread/exons.fa" in command
    assert "-o /work/gffread/output.gff" not in command
    assert [path.name for path in planned] == ["exons.fa"]
    assert GffReadNode.MAP_PLANNED_OUTPUTS(planned) == {"output_exons": planned[0]}


def test_gffread_supports_ensembl_track_spaces_and_native_dupinfo_syntax() -> None:
    conversion = {
        "input": "features.gtf",
        "input_format": "gtf",
        "gff_fmt": "gff",
        "ensembl": True,
        "tname": "track name",
        "output": "/work/gffread",
    }
    assert GffReadNode.VALIDATE_INPUTS(conversion) is True
    command = GffReadNode.render_command(conversion)
    assert "-t 'track name' -L -o /work/gffread/output.gff" in command
    merged = GffReadNode.render_command(
        {
            "input": "features.gtf",
            "merge_sel": "merge",
            "merge_options": ["dupinfo"],
            "output": "/work/gffread",
        }
    )
    assert "-d /work/gffread/dupinfo.txt" in merged
    assert "-d=" not in merged


def test_gffcompare_renames_single_input_maps_and_maps_multi_input_lists(tmp_path: Path) -> None:
    single = {
        "gffinputs": ["sample.gtf"],
        "element_identifiers": ["sample.gtf"],
        "output": "/work/gffcompare",
    }
    command = GffCompareNode.render_command(single)
    assert "mv /work/gffcompare/gffcmp.sample_gtf.tmap /work/gffcompare/output.tmap" in command
    single_planned = GffCompareNode.PLAN_OUTPUTS(single, tmp_path)
    assert GffCompareNode.MAP_PLANNED_OUTPUTS(single_planned)["tmap_output"] == single_planned[-1]

    multi = {"gffinputs": ["a.gtf", "b.gtf"], "element_identifiers": ["a.gtf", "b.gtf"]}
    multi_planned = GffCompareNode.PLAN_OUTPUTS(multi, tmp_path)
    mapped = GffCompareNode.MAP_PLANNED_OUTPUTS(multi_planned)
    assert isinstance(mapped["tmap_output"], list)
    assert len(mapped["tmap_output"]) == 2


def test_gffcompare_strict_duplicate_mode_requires_D() -> None:
    assert GffCompareNode.VALIDATE_INPUTS({"gffinputs": ["a.gtf"], "S": True}) == (
        "S requires duplication_selector=-D"
    )
    assert GffCompareNode.VALIDATE_INPUTS(
        {"gffinputs": ["a.gtf"], "S": True, "duplication_selector": "-D"}
    ) is True


def test_wigtobigwig_preserves_the_wrapper_error_text_scan() -> None:
    command = UcscWigToBigWigNode.render_command(
        {"input1": "track.wig", "index_len_path": "chrom.sizes", "output": "/work/wig"}
    )
    assert "needLargeMem: trying to allocate 0 bytes|^Error" in command
    assert "cat /work/wig/wigToBigWig.log >&2; exit 1" in command


def test_axtchain_requires_logical_format_and_enables_psl_explicitly() -> None:
    base = {"in_aln": "/cloud/alignment", "in_target": "target.fa", "in_query": "query.fa"}
    assert "alignment_format is required" in str(UcscAxtChainNode.VALIDATE_INPUTS(base))
    inputs = {**base, "alignment_format": "psl", "output": "/work/axtchain"}
    assert UcscAxtChainNode.VALIDATE_INPUTS(inputs) is True
    assert "axtChain -faQ -faT -psl" in UcscAxtChainNode.render_command(inputs)


def test_option_rich_chain_and_maf_filters_follow_source_argument_order() -> None:
    net_command = UcscNetFilterNode.render_command(
        {
            "in_net": "input.net",
            "syn_filter": "filtersyn",
            "syntype": "-chimpSyn",
            "minSynScore": 10,
            "minSynSize": 20,
            "minSynAli": 30,
            "minGap": 40,
            "output": "/work/netfilter",
        }
    )
    assert net_command == (
        "netFilter input.net -chimpSyn -minSynScore=10 -minSynSize=20 "
        "-minSynAli=30 -minGap=40 > /work/netfilter/out.ucsc.net"
    )
