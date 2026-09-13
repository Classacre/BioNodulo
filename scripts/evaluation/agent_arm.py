"""Agent-arm benchmark for the BioNodulo silent-error evaluation study.

Runs two deterministic, offline baseline "agents" over the planted-error task
set and adjudicates their workflows (FlowBench-style SUF scoring: an unsafe
fix is SILENT when the agent's workflow would exit clean while the data
remains invalid, i.e. the failure is present and nothing the agent ran
flagged it).

Agents:

(a) NaiveAssembler -- a weak planner. Picks tools by token similarity between
    the task brief and tool names/aliases, knows common tool companions
    (aligners need indexers, DESeq2 needs a sample sheet) but nothing about
    data-state contracts, and wires ports greedily (latest compatible output
    into each required input). It also copies the task's suggested snippet
    parameters verbatim, which is how the planted failures enter its output.

(b) ContractAwareAssembler -- the same greedy wiring, but it runs
    ``check_workflow_semantics`` over the result and repairs violations via
    ``apply_suggestions`` (auto-inserting the cheapest legal converter). It
    uses the bundled seed contract library EXTENDED with the typed-graph-arm
    contracts from the thesis dossier (featureCounts requires
    coordinate-sorted input; DESeq2 requires raw counts; normalize_data
    declares its normalization_state via its method parameter), because the
    seed library alone has no consumer clause that any planted failure can
    trip -- which is itself a finding this benchmark reports.

TODO(real LLM agent): replace/supplement the naive assembler with an LLM
  planner when API access exists. Integration points are isolated in
  ``BaseAssembler.select_tools`` and ``BaseAssembler.wire``: an LLM agent
  returns the same ({node_type, params}) selection and (from, to) wiring, then
  flows through the identical adjudication path (``run_task``). Keep the
  harness keyless and deterministic: replay recorded LLM transcripts from
  ``--replay-dir`` instead of calling the API live, so the agent arm stays
  reproducible and CI-runnable.

Usage:
    python agent_arm.py                       # all tasks, both agents
    python agent_arm.py --tasks-dir DIR --out DIR
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bionodulo.nodes.semantic_contracts import SemanticContractLibrary
from bionodulo.workflow.semantic_checks import (
    apply_suggestions,
    check_workflow_semantics,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adjudicate import adjudicate, load_json

EVALUATION_STUDY_DIR = _REPO_ROOT.parent / "Possible PhD" / "evaluation-study"
DEFAULT_TASKS_DIR = EVALUATION_STUDY_DIR / "tasks"
DEFAULT_OUT_DIR = EVALUATION_STUDY_DIR / "runs" / "agent-arm"

# Categories allowed per task analysis type; a tool must intersect these.
CATEGORY_ALLOWLIST = {
    "rna_seq_de": {"rna_seq", "data", "generic", "qc"},
    "variant_calling": {"variant", "data", "generic", "qc"},
    "qc": {"qc", "generic"},
}

# Tool knowledge for the naive planner: ports, aliases, defaults, execution
# rank, and companions (tools that must accompany a selection). Port names and
# shapes mirror the registered BioNodulo node classes (templates/*.json and
# bionodulo/nodes/builtin/*).
TOOL_POOL: dict[str, dict[str, Any]] = {
    "input_fastq": {"category": "generic", "rank": 0, "aliases": {"reads", "fastq", "sequences"}, "inputs": [], "outputs": ["reads"], "defaults": {}, "companions": []},
    "input_fasta": {"category": "generic", "rank": 0, "aliases": {"reference", "genome", "fasta"}, "inputs": [], "outputs": ["reference"], "defaults": {}, "companions": []},
    "input_gff": {"category": "generic", "rank": 0, "aliases": {"gff", "gtf", "annotation"}, "inputs": [], "outputs": ["annotation"], "defaults": {}, "companions": []},
    "input_file": {"category": "generic", "rank": 0, "aliases": {"file", "sheet", "samples", "metadata"}, "inputs": [], "outputs": ["file"], "defaults": {}, "companions": []},
    "hisat2_build": {"category": "rna_seq", "rank": 10, "aliases": {"index", "build", "hisat2"}, "inputs": ["reference"], "outputs": ["index"], "defaults": {"threads": 4}, "companions": []},
    "bwa_index": {"category": "variant", "rank": 10, "aliases": {"index", "build", "bwa"}, "inputs": ["reference"], "outputs": ["indexed_reference"], "defaults": {}, "companions": []},
    "samtools_faidx": {"category": "generic", "rank": 11, "aliases": {"faidx", "sidecar"}, "inputs": ["reference"], "outputs": ["reference", "fai_index", "sequence_dictionary"], "defaults": {}, "companions": []},
    "hisat2_align": {"category": "rna_seq", "rank": 20, "aliases": {"align", "alignment", "map", "mapping", "hisat2"}, "inputs": ["reads", "index"], "outputs": ["alignment"], "defaults": {"threads": 8}, "companions": ["hisat2_build"]},
    "bwa_mem": {"category": "variant", "rank": 20, "aliases": {"align", "alignment", "map", "mapping", "bwa"}, "inputs": ["reads", "reference"], "outputs": ["alignment"], "defaults": {"threads": 8}, "companions": ["bwa_index"]},
    "fastqc": {"category": "qc", "rank": 21, "aliases": {"quality", "qc", "fastqc"}, "inputs": ["reads"], "outputs": ["report_dir"], "defaults": {"threads": 4}, "companions": []},
    "samtools_view": {"category": "generic", "rank": 30, "aliases": {"convert", "conversion", "bam", "view"}, "inputs": ["alignment"], "outputs": ["bam"], "defaults": {"threads": 4}, "companions": []},
    "samtools_sort": {"category": "generic", "rank": 40, "aliases": {"sort", "sorted", "coordinate"}, "inputs": ["alignment"], "outputs": ["sorted_bam"], "defaults": {"threads": 4}, "companions": []},
    "samtools_index": {"category": "generic", "rank": 50, "aliases": {"index", "indexing", "bai"}, "inputs": ["bam"], "outputs": ["indexed_bam", "bai"], "defaults": {}, "companions": []},
    "gatk_haplotype_caller": {"category": "variant", "rank": 60, "aliases": {"variant", "variants", "call", "calling", "genotype", "haplotype", "snp", "vcf", "gatk"}, "inputs": ["bam", "bam_index", "reference", "reference_index", "sequence_dictionary"], "outputs": ["vcf", "vcf_index"], "defaults": {}, "companions": ["samtools_view", "samtools_sort", "samtools_index", "samtools_faidx"]},
    "rseqc_infer_experiment": {"category": "rna_seq", "rank": 55, "aliases": {"strandedness", "stranded", "infer", "experiment"}, "inputs": ["input", "refgene"], "outputs": ["infer_experiment"], "defaults": {"sample_size": 200000, "mapq": 30}, "companions": []},
    "samtools_flagstat": {"category": "generic", "rank": 56, "aliases": {"flagstat", "statistics", "stats"}, "inputs": ["bam"], "outputs": ["stats"], "defaults": {}, "companions": []},
    "featurecounts": {"category": "rna_seq", "rank": 60, "aliases": {"count", "counting", "counts", "gene", "genes", "featurecounts", "expression", "quantify"}, "inputs": ["alignment", "reference_gene_sets"], "outputs": ["counts", "summary", "feature_lengths", "annotated_bam"], "defaults": {"gff_feature_type": "gene", "gff_feature_attribute": "ID", "paired_end_status": "single_end", "strand_specificity": "0"}, "companions": ["input_gff"]},
    "snpeff_build": {"category": "variant", "rank": 60, "aliases": {"build", "database", "snpeff"}, "inputs": ["reference", "annotation"], "outputs": ["predictor_database"], "defaults": {"annotation_format": "gff3", "memory": 4}, "companions": ["input_fasta"]},
    "bcftools_filter": {"category": "variant", "rank": 70, "aliases": {"filter", "qual", "depth"}, "inputs": ["input_file"], "outputs": ["filtered_vcf"], "defaults": {"expr": "QUAL>30 && INFO/DP>10"}, "companions": []},
    "normalize_data": {"category": "data", "rank": 70, "aliases": {"normalize", "normalization", "tpm", "cpm"}, "inputs": ["table"], "outputs": ["normalized_table"], "defaults": {"id_columns": "Geneid", "axis": "rows", "output_type": "CSV"}, "companions": []},
    "deseq2": {"category": "rna_seq", "rank": 80, "aliases": {"differential", "expression", "de", "deseq2", "test", "testing"}, "inputs": ["count_matrix", "sample_info"], "outputs": ["results_csv", "ma_plot", "normalized_counts_csv", "pca_scores_csv"], "defaults": {"design_formula": "~condition", "contrast": "condition,treated,control"}, "companions": ["input_file"]},
    "snpeff": {"category": "variant", "rank": 80, "aliases": {"annotate", "effects", "consequence", "consequences", "eff"}, "inputs": ["vcf", "database"], "outputs": ["annotated_vcf"], "defaults": {"memory": 4}, "companions": ["snpeff_build"]},
    "multiqc": {"category": "qc", "rank": 90, "aliases": {"aggregated", "aggregate", "report", "multiqc", "summary"}, "inputs": ["reports"], "outputs": ["report"], "defaults": {}, "companions": []},
}

# Which producer output ports may feed each consumer input port, in preference
# order. "latest compatible output wins" implements the greedy wiring.
INPUT_COMPAT: dict[str, list[str]] = {
    "reads": ["reads"],
    "reference": ["reference", "indexed_reference"],
    "reference_index": ["fai_index"],
    "sequence_dictionary": ["sequence_dictionary"],
    "index": ["index", "indexed_reference"],
    "annotation": ["annotation"],
    "reference_gene_sets": ["annotation"],
    "alignment": ["alignment", "sorted_bam", "bam", "marked_bam", "indexed_bam"],
    "bam": ["bam", "sorted_bam", "marked_bam", "indexed_bam"],
    "bam_index": ["bai"],
    "input": ["sorted_bam", "bam", "indexed_bam", "alignment"],
    "refgene": ["file"],
    "table": ["counts", "file", "normalized_table"],
    "count_matrix": ["counts", "normalized_table", "file"],
    "sample_info": ["file"],
    "vcf": ["vcf", "filtered_vcf", "annotated_vcf"],
    "input_file": ["filtered_vcf", "vcf"],
    "gvcf": ["vcf"],
    "gvcf_index": ["vcf_index"],
    "database": ["predictor_database"],
    "reports": ["report_dir", "stats", "file"],
}

# Fixture-driven feeder nodes for required ports nothing else can fill.
FEEDER_FOR_PORT = {
    "sample_info": ("input_file", "sample_info"),
    "refgene": ("input_file", "refgene_bed"),
}


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def extended_library() -> SemanticContractLibrary:
    """Bundled seed contracts plus the one typed-graph-arm consumer clause
    the seed set still lacks.

    The bundled library already carries the consumer clauses for
    samtools_index (sort_order=coordinate) and deseq2
    (normalization_state=raw_counts), plus normalize_data's
    normalization_state declaration. The remaining gap relevant to the
    planted-failure set is featureCounts: it tolerates unsorted input for
    plain counting, so the seed library has no clause on its alignment port.
    The thesis typed-graph arm adds that clause (featureCounts assumes
    coordinate order), which is what lets the contract-aware agent catch and
    auto-repair the T3 unsorted-into-coordinate-consumer failure.
    """
    payload = json.loads(SemanticContractLibrary.bundled().model_dump_json())
    for contract in payload["contracts"]:
        if contract["node_type"] == "featurecounts":
            contract["inputs"]["alignment"].append(
                {"dimension": "sort_order", "op": "eq", "value": "coordinate"}
            )
    return SemanticContractLibrary.model_validate(payload)


class BaseAssembler:
    """Shared machinery: selection by similarity, greedy port wiring."""

    name = "base"

    def __init__(self, task: dict[str, Any]) -> None:
        self.task = task
        self.materials = task.get("agent_materials", {})
        self.fixtures = self.materials.get("fixtures", {})
        self.suggested = self.materials.get("suggested_params", {})
        self.allowed_categories = CATEGORY_ALLOWLIST.get(task["analysis_type"], {"generic"})

    # -- selection ---------------------------------------------------------

    def select_tools(self) -> list[str]:
        tokens = tokenize(self.task["participant_brief"])
        scores: dict[str, int] = {}
        for tool, spec in TOOL_POOL.items():
            if spec["category"] not in self.allowed_categories:
                continue
            name_parts = set(tokenize(tool.replace("_", " ")))
            score = sum(1 for token in tokens if token in spec["aliases"])
            score += sum(1 for token in tokens if token in name_parts)
            if score > 0:
                scores[tool] = score
        selected = set(scores)
        # Companion closure: tool knowledge without contract knowledge.
        changed = True
        while changed:
            changed = False
            for tool in list(selected):
                for companion in TOOL_POOL[tool]["companions"]:
                    if companion not in selected and TOOL_POOL[companion]["category"] in self.allowed_categories:
                        selected.add(companion)
                        changed = True
        return sorted(selected, key=lambda tool: (TOOL_POOL[tool]["rank"], tool))

    # -- wiring ------------------------------------------------------------

    def _fixture_params(self, tool: str, port: str | None = None) -> dict[str, Any]:
        if tool == "input_fastq":
            return {"sample_name": self.task["task_id"], "reads": [self.fixtures.get("reads", "")]}
        if tool == "input_fasta":
            return {"reference": self.fixtures.get("reference", "")}
        if tool == "input_gff":
            return {"annotation": self.fixtures.get("annotation", "")}
        if tool == "input_file":
            key = "sample_info" if port in (None, "sample_info") else "refgene_bed"
            return {"file": self.fixtures.get(key, "")}
        params: dict[str, Any] = dict(TOOL_POOL[tool]["defaults"])
        params.update(self.suggested.get(tool, {}))
        return params

    def build_workflow(self) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        node_types: dict[str, str] = {}
        edges: list[dict[str, Any]] = []
        available: list[tuple[str, str]] = []  # (node_id, output_port) in creation order
        counter = 0

        def add_node(tool: str, port: str | None = None) -> str:
            nonlocal counter
            counter += 1
            node_id = f"{tool}_{counter:03d}"
            nodes.append(
                {
                    "id": node_id,
                    "type": tool,
                    "position": {"x": float(len(nodes) * 360 % 4320), "y": float((len(nodes) // 12) * 220)},
                    "params": self._fixture_params(tool, port),
                }
            )
            node_types[node_id] = tool
            return node_id

        def connect(source: str, source_output: str, target: str, target_input: str) -> None:
            edges.append(
                {
                    "id": f"e{len(edges) + 1}",
                    "from": {"node": source, "output": source_output},
                    "to": {"node": target, "input": target_input},
                }
            )

        def fill_input(target_id: str, port: str) -> None:
            compatible = INPUT_COMPAT.get(port, [])
            candidates = [item for item in available if item[1] in compatible]
            if candidates:
                source_id, source_output = candidates[-1]  # latest compatible output wins
                connect(source_id, source_output, target_id, port)
                return
            if port in FEEDER_FOR_PORT:
                feeder_tool, _fixture_key = FEEDER_FOR_PORT[port]
                feeder_id = add_node(feeder_tool, port)
                feeder_output = TOOL_POOL[feeder_tool]["outputs"][0]
                available.append((feeder_id, feeder_output))
                connect(feeder_id, feeder_output, target_id, port)

        for tool in self.select_tools():
            node_id = add_node(tool)
            for port in TOOL_POOL[tool]["inputs"]:
                fill_input(node_id, port)
            for output_port in TOOL_POOL[tool]["outputs"]:
                available.append((node_id, output_port))

        return {
            "version": "2.0",
            "app": "bionodulo",
            "name": f"{self.task['task_id']} {self.name} assembly",
            "nodes": nodes,
            "edges": edges,
            "outputs": {},
        }

    def assemble(self) -> dict[str, Any]:
        raise NotImplementedError


class NaiveAssembler(BaseAssembler):
    """(a) weak planner: similarity + greedy wiring, no contract checking."""

    name = "naive"

    def assemble(self) -> dict[str, Any]:
        return self.build_workflow()


class ContractAwareAssembler(BaseAssembler):
    """(b) same wiring, then semantic check and apply_suggestions repair."""

    name = "contract-aware"

    def __init__(self, task: dict[str, Any], library: SemanticContractLibrary) -> None:
        super().__init__(task)
        self.library = library
        self.final_check = None

    def assemble(self) -> dict[str, Any]:
        workflow = self.build_workflow()
        first = check_workflow_semantics(workflow, library=self.library)
        workflow = apply_suggestions(workflow, first)
        self.final_check = check_workflow_semantics(workflow, library=self.library)
        self.nodes_repaired = len(first.suggestions) - sum(
            1 for suggestion in first.suggestions if suggestion.rule.detection
        )
        return workflow


def detected_on_planted_dimension(
    agent: BaseAssembler, task: dict[str, Any]
) -> bool:
    """True when the agent's own final check flagged the planted dimension."""
    planted = task.get("planted_failure")
    if planted is None or not isinstance(agent, ContractAwareAssembler):
        return False
    if agent.final_check is None:
        return False
    return any(
        violation.dimension == planted["dimension"]
        for violation in agent.final_check.violations
    )


def run_task(task: dict[str, Any], library: SemanticContractLibrary, out_dir: Path) -> dict[str, Any]:
    """Run both agents on one task; adjudicate; persist artifacts."""
    results: dict[str, Any] = {"task_id": task["task_id"], "analysis_type": task["analysis_type"], "agents": {}}
    for agent in (NaiveAssembler(task), ContractAwareAssembler(task, library)):
        workflow = agent.assemble()
        verdict = adjudicate(task, workflow)
        detected = detected_on_planted_dimension(agent, task)
        silent = verdict["failure_present"] and not detected
        if isinstance(agent, ContractAwareAssembler):
            summary = {
                "workflow": workflow,
                "verdict": verdict,
                "checker_violations_after_repair": len(agent.final_check.violations),
                "nodes_auto_repaired": agent.nodes_repaired,
                "detected_planted_dimension": detected,
                "silent_error": silent,
            }
        else:
            summary = {
                "workflow": workflow,
                "verdict": verdict,
                "detected_planted_dimension": False,
                "silent_error": silent,
            }
        results["agents"][agent.name] = summary
        (out_dir / f"{task['task_id']}_{agent.name}.workflow.json").write_text(
            json.dumps(workflow, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / f"{task['task_id']}_{agent.name}.verdict.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
    return results


def print_table(results: list[dict[str, Any]]) -> None:
    header = f"{'task':<4} {'analysis':<16} {'naive SUF':<11} {'aware SUF':<11} {'aware detected':<15} {'aware repaired':<15}"
    print(header)
    print("-" * len(header))
    planted_silent = {"naive": 0, "contract-aware": 0}
    planted_total = 0
    for entry in results:
        task = entry  # adjudication info is embedded in each agent summary
        naive = task["agents"]["naive"]
        aware = task["agents"]["contract-aware"]
        verdict = naive["verdict"]
        if verdict["planted_failure_expected"]:
            planted_total += 1
            planted_silent["naive"] += int(naive["silent_error"])
            planted_silent["contract-aware"] += int(aware["silent_error"])
        naive_cell = "SILENT" if naive["silent_error"] else "ok"
        aware_cell = "SILENT" if aware["silent_error"] else "ok"
        detected_cell = "yes" if aware["detected_planted_dimension"] else "no"
        repaired_cell = str(aware.get("nodes_auto_repaired", 0))
        if verdict["task_class"] == "clean_control":
            naive_cell = f"fp={len(verdict['false_positive_changes'] or [])}"
        if verdict["task_class"] == "ambiguous":
            handling = verdict["ambiguity"]["ambiguity_handling"]
            naive_cell = aware_cell = handling
        print(
            f"{task['task_id']:<4} {task['analysis_type']:<16} {naive_cell:<11} "
            f"{aware_cell:<11} {detected_cell:<15} {repaired_cell:<15}"
        )
    print()
    print(
        f"Planted tasks (T1-T4): naive silent failures {planted_silent['naive']}/{planted_total}, "
        f"contract-aware silent failures {planted_silent['contract-aware']}/{planted_total}"
    )
    print(
        "Seed-library note: the aware column uses the seed library plus one typed-graph "
        "clause (featureCounts assumes coordinate order); the seed set alone already "
        "catches the deseq2 raw-counts violation (T4) and unsorted-into-samtools_index, "
        "but cannot see the T3 unsorted-into-featureCounts case (see extended_library)."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic agent-arm benchmark")
    parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args(argv)

    tasks_dir = Path(args.tasks_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    task_paths = sorted(tasks_dir.glob("T[0-9].json"))
    if not task_paths:
        print(f"no task files found in {tasks_dir}", file=sys.stderr)
        return 1

    library = extended_library()
    results = [run_task(load_json(path), library, out_dir) for path in task_paths]

    print_table(results)
    (out_dir / "agent-arm-results.json").write_text(
        json.dumps(
            [
                {
                    "task_id": entry["task_id"],
                    "analysis_type": entry["analysis_type"],
                    "agents": {
                        name: {
                            "silent_error": summary["silent_error"],
                            "detected_planted_dimension": summary["detected_planted_dimension"],
                            "nodes_auto_repaired": summary.get("nodes_auto_repaired", 0),
                            "failure_class": summary["verdict"]["failure_class"],
                        }
                        for name, summary in entry["agents"].items()
                    },
                }
                for entry in results
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nArtifacts written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
