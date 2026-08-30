from __future__ import annotations

import json
import random
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.ml_design_family import (
    BedmethylFeatureBuilderNode,
    BestSoFarNode,
    CandidateGeneratorNode,
    GroupRelativeOptimizerNode,
    MultiObjectiveScorerNode,
    PolicySamplerNode,
    SimplePredictorScoreNode,
    SimplePredictorTrainNode,
)
from bionodulo.nodes.builtin.ml_design_family.adapter import (
    AMINO_ACID_CODONS,
    CODON_AMINO_ACID,
)
from bionodulo.nodes.registry import NodeRegistry

FAMILY = "bionodulo.nodes.builtin.ml_design_family"
NODE_MODULES = {
    "candidate_generator": "candidate_generator",
    "multi_objective_scorer": "multi_objective_scorer",
    "group_relative_optimizer": "group_relative_optimizer",
    "best_so_far": "best_so_far",
    "policy_sampler": "policy_sampler",
    "bedmethyl_feature_builder": "bedmethyl_feature_builder",
    "simple_predictor_train": "simple_predictor_train",
    "simple_predictor_score": "simple_predictor_score",
    "campaign_config_builder": "campaign_config_builder",
    "campaign_results_builder": "campaign_results_builder",
    "paired_stats": "paired_stats",
    "openvaccine_prepare": "openvaccine_prepare",
    "training_leakage_check": "training_leakage_check",
}
PREFERRED_CODONS = {
    "GCT", "CGT", "AAT", "GAT", "TGT", "CAA", "GAA", "GGT", "CAT", "ATT",
    "TTA", "AAA", "ATG", "TTT", "CCT", "TCT", "ACT", "GTT", "TGG", "TAT",
}


def _context(tmp_path: Path, name: str = "run") -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(node_dir=node_dir)


def _base_cds(seed: int = 7, n_codons: int = 300) -> str:
    rng = random.Random(seed)
    amino_acids = sorted(AMINO_ACID_CODONS)
    protein = ["M"] + [rng.choice(amino_acids) for _ in range(n_codons - 1)]
    return "".join(AMINO_ACID_CODONS[amino_acid][0] for amino_acid in protein)


def _gc(cds: str) -> float:
    return sum(char in "GC" for char in cds) / len(cds)


def _cai(cds: str) -> float:
    codons = [cds[index : index + 3] for index in range(0, len(cds), 3)]
    return sum(codon in PREFERRED_CODONS for codon in codons) / len(codons)


def _objective_payload(candidates_path: str, objective: str) -> str:
    entries = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
    scorer = _gc if objective == "gc" else _cai
    return json.dumps([{"id": entry["id"], "score": scorer(entry["cds"])} for entry in entries])


def _raw_composites(candidates_path: str) -> list[dict[str, Any]]:
    entries = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
    return [{"id": entry["id"], "composite": _gc(entry["cds"]) + _cai(entry["cds"])} for entry in entries]


def test_registry_resolves_each_node_to_its_focused_module() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    expected = {node_id: f"{FAMILY}.{module}" for node_id, module in NODE_MODULES.items()}
    assert {node_id: registry.get(node_id).__module__ for node_id in expected} == expected
    for node_id in expected:
        node_class = registry.get(node_id)
        assert node_class.CATEGORY == "ml_design"
        assert node_class.REQUIRES_EXTERNAL_TOOLS is False
        assert node_class.REQUIRED_EXECUTABLES == []
        assert len(node_class.RETURN_TYPES) == len(node_class.RETURN_NAMES)


def test_optimizer_cites_grpo_papers() -> None:
    assert GroupRelativeOptimizerNode.CITATION_URLS == [
        "https://arxiv.org/abs/2402.03300",
        "https://arxiv.org/abs/2605.01513",
    ]
    assert SimplePredictorTrainNode.REQUIRED_CONDA_PACKAGES == ["numpy"]
    assert SimplePredictorScoreNode.REQUIRED_CONDA_PACKAGES == ["numpy"]


@pytest.mark.asyncio
async def test_candidate_generator_strategies_are_deterministic_and_synonymous(tmp_path: Path) -> None:
    base = _base_cds()
    node = CandidateGeneratorNode()
    context = _context(tmp_path)

    first = await node.run(base_cds=base, n_candidates=24, seed=3, context=context)
    second = await node.run(base_cds=base, n_candidates=24, seed=3, context=context)
    assert first == second
    assert Path(first[0]).is_file() and Path(first[1]).is_file()

    entries = json.loads(Path(first[0]).read_text(encoding="utf-8"))
    assert len(entries) == 24
    assert [entry["id"] for entry in entries] == [f"cand_{index:04d}" for index in range(24)]
    base_protein = [CODON_AMINO_ACID[base[i : i + 3]] for i in range(0, len(base), 3)]
    for entry in entries:
        assert len(entry["cds"]) == len(base)
        protein = [CODON_AMINO_ACID[entry["cds"][i : i + 3]] for i in range(0, len(entry["cds"]), 3)]
        assert protein == base_protein

    fasta = Path(first[1]).read_text(encoding="utf-8").splitlines()
    assert fasta[0] == ">cand_0000"
    assert sum(line.startswith(">") for line in fasta) == 24
    assert "".join(line for line in fasta[1:16]) == entries[0]["cds"]

    weighted = await node.run(
        base_cds="ATG" + "AAG" * 10 + "TTT" * 5,
        n_candidates=8,
        seed=3,
        strategy="synonymous_weighted",
        codon_weights=json.dumps({"AAA": 100.0}),
        context=_context(tmp_path, "weighted"),
    )
    weighted_entries = json.loads(Path(weighted[0]).read_text(encoding="utf-8"))
    lysine_positions = [index for index in range(3, 33, 3)]
    aaa_uses = sum(
        entry["cds"][position : position + 3] == "AAA"
        for entry in weighted_entries
        for position in lysine_positions
    )
    assert aaa_uses > 0.8 * len(weighted_entries) * len(lysine_positions)

    jitter = await node.run(
        base_cds=base,
        n_candidates=24,
        seed=3,
        strategy="gc_jitter",
        gc_target=1.0,
        gc_sharpness=50.0,
        context=_context(tmp_path, "jitter"),
    )
    uniform = await node.run(
        base_cds=base, n_candidates=24, seed=3, strategy="synonymous_uniform", context=_context(tmp_path, "uniform")
    )
    jitter_entries = json.loads(Path(jitter[0]).read_text(encoding="utf-8"))
    uniform_entries = json.loads(Path(uniform[0]).read_text(encoding="utf-8"))
    assert mean_gc(jitter_entries) > mean_gc(uniform_entries)


def mean_gc(entries: list[dict[str, Any]]) -> float:
    return sum(_gc(entry["cds"]) for entry in entries) / len(entries)


@pytest.mark.asyncio
async def test_candidate_generator_rejects_invalid_inputs(tmp_path: Path) -> None:
    node = CandidateGeneratorNode()
    cases: tuple[tuple[dict[str, Any], str], ...] = (
        ({"base_cds": ""}, "base_cds' must be a non-empty"),
        ({"base_cds": "ATGGGGT"}, "multiple of three"),
        ({"base_cds": "ATGX"}, "non-ACGT"),
        ({"base_cds": "ATGTAATTT", "n_candidates": 24}, "stop codon"),
        ({"base_cds": "ATGGGGTTTAAA", "n_candidates": 2000}, "n_candidates' must be at most 1000"),
        ({"base_cds": "ATGGGGTTTAAA", "n_candidates": -1}, "n_candidates' must be at least 0"),
        ({"base_cds": "ATGGGGTTTAAA", "strategy": "nope"}, "strategy' must be one of"),
        (
            {"base_cds": "ATGGGGTTTAAA", "strategy": "synonymous_weighted"},
            "codon_weights' is required",
        ),
        (
            {
                "base_cds": "ATGGGGTTTAAA",
                "strategy": "synonymous_weighted",
                "codon_weights": json.dumps({"ZZZ": 1.0}),
            },
            "unknown codon",
        ),
        (
            {
                "base_cds": "ATGGGGTTTAAA",
                "strategy": "synonymous_weighted",
                "codon_weights": json.dumps({"AAA": -1}),
            },
            "positive number",
        ),
    )
    for updates, message in cases:
        inputs: dict[str, Any] = {"base_cds": "ATGGGGTTTAAA", "n_candidates": 4}
        inputs.update(updates)
        result = node.VALIDATE_INPUTS(inputs)
        assert message in str(result), (updates, result)

    with pytest.raises(ValueError, match="must be a non-empty"):
        await node.run(base_cds="", context=_context(tmp_path))

    # n_candidates=0 is the empty-batch guard: it validates and emits an
    # explicitly empty candidates JSON + empty FASTA instead of erroring.
    empty_json, empty_fasta = await node.run(
        base_cds="ATGGGGTTTAAA", n_candidates=0, context=_context(tmp_path, "zero")
    )
    assert json.loads(Path(empty_json).read_text(encoding="utf-8")) == []
    assert Path(empty_fasta).read_text(encoding="utf-8").strip() == ""


@pytest.mark.asyncio
async def test_multi_objective_scorer_weights_modes_and_ranking(tmp_path: Path) -> None:
    base = _base_cds()
    candidates = (
        await CandidateGeneratorNode().run(base_cds=base, n_candidates=24, seed=5, context=_context(tmp_path))
    )[0]
    gc_scores = _objective_payload(candidates, "gc")
    cai_scores = _objective_payload(candidates, "cai")

    ranked, table = await MultiObjectiveScorerNode().run(
        candidates=candidates,
        scores_1=gc_scores,
        scores_2=cai_scores,
        weights=json.dumps({"scores_1": 2.0, "scores_2": 1.0}),
        modes=json.dumps({"scores_2": "minimize"}),
        context=_context(tmp_path, "score"),
    )
    entries = json.loads(Path(ranked).read_text(encoding="utf-8"))
    assert len(entries) == 24
    composites = [entry["composite"] for entry in entries]
    assert composites == sorted(composites, reverse=True)
    for entry in entries:
        assert set(entry["per_objective"]) == {"scores_1", "scores_2"}
    tsv_lines = Path(table).read_text(encoding="utf-8").splitlines()
    assert tsv_lines[0].split("\t") == ["id", "composite", "scores_1", "scores_2"]
    assert len(tsv_lines) == 25

    minimize_only, _ = await MultiObjectiveScorerNode().run(
        candidates=candidates,
        scores_1=gc_scores,
        modes=json.dumps({"scores_1": "minimize"}),
        context=_context(tmp_path, "min"),
    )
    flipped = json.loads(Path(minimize_only).read_text(encoding="utf-8"))
    gc_by_id = {entry["id"]: _gc(next(e["cds"] for e in json.loads(Path(candidates).read_text(encoding="utf-8")) if e["id"] == entry["id"])) for entry in entries}
    assert gc_by_id[flipped[0]["id"]] == min(gc_by_id.values())
    assert gc_by_id[flipped[-1]["id"]] == max(gc_by_id.values())

    tsv_scores = tmp_path / "scores.tsv"
    tsv_scores.write_text("id\tscore\n" + "".join(
        f"{entry['id']}\t{entry['score']}\n" for entry in json.loads(gc_scores)
    ), encoding="utf-8")
    from_tsv, _ = await MultiObjectiveScorerNode().run(
        candidates=candidates, scores_1=tsv_scores, context=_context(tmp_path, "tsv")
    )
    assert json.loads(Path(from_tsv).read_text(encoding="utf-8"))[0]["id"] == flipped[-1]["id"]


@pytest.mark.asyncio
async def test_multi_objective_scorer_rejects_malformed_and_scores_intersections(tmp_path: Path) -> None:
    base = _base_cds()
    candidates = (
        await CandidateGeneratorNode().run(base_cds=base, n_candidates=8, seed=5, context=_context(tmp_path))
    )[0]
    entries = json.loads(Path(candidates).read_text(encoding="utf-8"))
    valid = json.dumps([{"id": entry["id"], "score": 1.0} for entry in entries])

    # Partial id coverage is tolerated: only the intersection is scored and
    # the skipped ids are documented in a provenance footer on the TSV.
    partial = json.dumps([{"id": entries[0]["id"], "score": 1.0}])
    with_ghost = json.dumps(
        [{"id": entry["id"], "score": 1.0} for entry in entries] + [{"id": "ghost", "score": 2.0}]
    )
    ranked, table = await MultiObjectiveScorerNode().run(
        candidates=candidates, scores_1=partial, context=_context(tmp_path, "partial")
    )
    payload = json.loads(Path(ranked).read_text(encoding="utf-8"))
    assert [entry["id"] for entry in payload] == [entries[0]["id"]]
    table_text = Path(table).read_text(encoding="utf-8")
    assert "<!--" in table_text and "skipped 7 candidate(s)" in table_text

    ghost_ranked, _ = await MultiObjectiveScorerNode().run(
        candidates=candidates, scores_1=with_ghost, context=_context(tmp_path, "ghost")
    )
    ghost_ids = [entry["id"] for entry in json.loads(Path(ghost_ranked).read_text(encoding="utf-8"))]
    assert "ghost" not in ghost_ids and len(ghost_ids) == len(entries)

    cases: tuple[tuple[dict[str, Any], str], ...] = (
        ({"scores_1": json.dumps([{"id": entry["id"], "score": "abc"} for entry in entries])}, "not numeric"),
        ({"scores_1": valid, "weights": "{not json"}, "must be a JSON object"),
        ({"scores_1": valid, "weights": json.dumps({"bogus": 1.0})}, "scores_N input name"),
        ({"scores_1": valid, "modes": json.dumps({"scores_1": "sideways"})}, "must be one of"),
    )
    for updates, message in cases:
        inputs: dict[str, Any] = {"candidates": candidates, "scores_1": valid}
        inputs.update(updates)
        result = MultiObjectiveScorerNode.VALIDATE_INPUTS(inputs) if "weights" in updates or "modes" in updates else None
        if result is not None:
            assert message in str(result), (updates, result)
            continue
        with pytest.raises(ValueError, match=message):
            await MultiObjectiveScorerNode().run(
                candidates=inputs["candidates"], scores_1=inputs["scores_1"], context=_context(tmp_path)
            )

    with pytest.raises(ValueError, match="header must contain"):
        bad = tmp_path / "bad.tsv"
        bad.write_text("id\tvalue\nr0\t1.0\n", encoding="utf-8")
        await MultiObjectiveScorerNode().run(candidates=candidates, scores_1=bad, context=_context(tmp_path))


async def _run_design_iteration(
    tmp_path: Path,
    base: str,
    candidates_path: str,
    policy_table: str | None,
    iteration: int,
) -> tuple[str, str, dict[str, Any]]:
    context = _context(tmp_path, f"iter{iteration}")
    if policy_table is None:
        candidates_path = (
            await CandidateGeneratorNode().run(
                base_cds=base, n_candidates=48, seed=1, context=context
            )
        )[0]
    else:
        candidates_path = (
            await PolicySamplerNode().run(
                base_cds=base,
                policy_table=policy_table,
                n_candidates=48,
                seed=10 + iteration,
                context=context,
            )
        )[0]
    ranked = (
        await MultiObjectiveScorerNode().run(
            candidates=candidates_path,
            scores_1=_objective_payload(candidates_path, "gc"),
            scores_2=_objective_payload(candidates_path, "cai"),
            context=context,
        )
    )[0]
    policy, elites, best = await GroupRelativeOptimizerNode().run(
        candidates=candidates_path,
        ranked=ranked,
        top_k=8,
        learning_rate=10.0,
        ref_strength=0.01,
        context=context,
    )
    return policy, candidates_path, json.loads(Path(elites).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_optimizer_improves_objective_across_seeded_iterations(tmp_path: Path) -> None:
    base = _base_cds()
    policy: str | None = None
    batch_means: list[float] = []
    batch_bests: list[float] = []
    best_payload: str | None = None
    best_score: float | None = None
    for iteration in range(4):
        policy, candidates_path, elite_payload = await _run_design_iteration(
            tmp_path, base, "", policy, iteration
        )
        raw = {entry["id"]: entry["composite"] for entry in _raw_composites(candidates_path)}
        batch_means.append(sum(raw.values()) / len(raw))
        batch_bests.append(max(raw.values()))
        assert elite_payload["stats"]["improvement_vs_prev"] is None

        updated, improved, score = await BestSoFarNode().run(
            incoming=json.dumps(_raw_composites(candidates_path)),
            current=best_payload,
            context=_context(tmp_path, f"best{iteration}"),
        )
        if best_score is None or score > best_score:
            assert improved is True
            best_score = score
        else:
            assert improved is False
        best_payload = updated

    assert batch_bests[-1] > batch_bests[0]
    assert batch_means[-1] > batch_means[0]
    tracked = json.loads(Path(best_payload).read_text(encoding="utf-8"))
    assert tracked["composite"] >= max(batch_bests) - 1e-9


@pytest.mark.asyncio
async def test_optimizer_policy_update_floors_probabilities_and_tracks_improvement(tmp_path: Path) -> None:
    base = _base_cds(n_codons=60)
    context = _context(tmp_path)
    candidates = (
        await CandidateGeneratorNode().run(base_cds=base, n_candidates=24, seed=2, context=context)
    )[0]
    ranked = (
        await MultiObjectiveScorerNode().run(
            candidates=candidates, scores_1=_objective_payload(candidates, "gc"), context=context
        )
    )[0]
    policy_path, elites_path, best_path = await GroupRelativeOptimizerNode().run(
        candidates=candidates,
        ranked=ranked,
        top_k=8,
        temperature=0.5,
        epsilon=0.05,
        ref_strength=0.2,
        previous_best_composite=-1.0,
        context=context,
    )
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    assert policy["format"] == "categorical_codon_policy_v1"
    assert policy["n_positions"] == 60
    for position, distribution in policy["positions"].items():
        total = sum(distribution.values())
        assert abs(total - 1.0) < 1e-6
        assert min(distribution.values()) >= 0.05 - 1e-9

    elites = json.loads(Path(elites_path).read_text(encoding="utf-8"))
    assert len(elites["elites"]) == 8
    composites = [elite["composite"] for elite in elites["elites"]]
    assert composites == sorted(composites, reverse=True)
    assert elites["best"]["composite"] == composites[0]
    stats = elites["stats"]
    assert stats["best_composite"] == composites[0]
    assert stats["improvement_vs_prev"] == pytest.approx(composites[0] + 1.0)
    assert stats["std"] >= 0.0
    best = json.loads(Path(best_path).read_text(encoding="utf-8"))
    assert best["id"] == elites["best"]["id"]

    resampled = (
        await PolicySamplerNode().run(
            base_cds=base, policy_table=policy_path, n_candidates=16, seed=4, context=context
        )
    )[0]
    entries = json.loads(Path(resampled).read_text(encoding="utf-8"))
    assert len(entries) == 16
    base_protein = [CODON_AMINO_ACID[base[i : i + 3]] for i in range(0, len(base), 3)]
    for entry in entries:
        protein = [CODON_AMINO_ACID[entry["cds"][i : i + 3]] for i in range(0, len(entry["cds"]), 3)]
        assert protein == base_protein

    fallback = (
        await PolicySamplerNode().run(base_cds=base, n_candidates=4, seed=4, context=context)
    )[0]
    assert len(json.loads(Path(fallback).read_text(encoding="utf-8"))) == 4


@pytest.mark.asyncio
async def test_optimizer_rejects_drifted_candidates_and_broken_policy(tmp_path: Path) -> None:
    base = _base_cds(n_codons=30)
    context = _context(tmp_path)
    candidates = (
        await CandidateGeneratorNode().run(base_cds=base, n_candidates=8, seed=2, context=context)
    )[0]
    ranked = (
        await MultiObjectiveScorerNode().run(
            candidates=candidates, scores_1=_objective_payload(candidates, "gc"), context=context
        )
    )[0]
    entries = json.loads(Path(candidates).read_text(encoding="utf-8"))

    original_codon = entries[0]["cds"][3:6]
    replacement = next(
        codon
        for codon in sorted(CODON_AMINO_ACID)
        if codon != original_codon and CODON_AMINO_ACID[codon] != CODON_AMINO_ACID[original_codon]
    )
    mutated = json.dumps(
        [
            {**entry, "cds": entry["cds"][:3] + replacement + entry["cds"][6:]} if index == 0 else entry
            for index, entry in enumerate(entries)
        ]
    )
    with pytest.raises(ValueError, match="one identical protein"):
        await GroupRelativeOptimizerNode().run(candidates=mutated, ranked=ranked, context=context)

    # Partial coverage is tolerated: candidates absent from ranked are dropped
    # and the optimizer updates the policy over the covered subset.
    ranked_entries = json.loads(Path(ranked).read_text(encoding="utf-8"))
    truncated_ranked = json.dumps(ranked_entries[:-2])
    subset_policy, subset_elites, subset_best = await GroupRelativeOptimizerNode().run(
        candidates=candidates, ranked=truncated_ranked, context=context
    )
    subset_payload = json.loads(Path(subset_elites).read_text(encoding="utf-8"))
    assert subset_payload["stats"]["n_candidates"] == len(ranked_entries) - 2
    assert len(subset_payload["elites"]) == len(ranked_entries) - 2
    assert json.loads(Path(subset_best).read_text(encoding="utf-8"))["id"] == subset_payload["best"]["id"]

    bad_policy = tmp_path / "policy.json"
    bad_policy.write_text(json.dumps({"positions": {"0": {"AAA": 1.0}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="positions must cover"):
        await GroupRelativeOptimizerNode().run(
            candidates=candidates, ranked=ranked, policy_table=bad_policy, context=context
        )

    assert "top_k' must be at least 1" in str(
        GroupRelativeOptimizerNode.VALIDATE_INPUTS({"candidates": candidates, "ranked": ranked, "top_k": 0})
    )


@pytest.mark.asyncio
async def test_best_so_far_tracks_max_and_min_modes(tmp_path: Path) -> None:
    context = _context(tmp_path)
    incoming = json.dumps([{"id": "a", "composite": 1.0}, {"id": "b", "composite": 3.0}])

    best, improved, score = await BestSoFarNode().run(incoming=incoming, context=context)
    assert improved is True and score == 3.0
    assert json.loads(Path(best).read_text(encoding="utf-8"))["id"] == "b"

    same, improved, score = await BestSoFarNode().run(incoming=incoming, current=best, context=context)
    assert improved is False and score == 3.0 and same == best

    lower, improved, score = await BestSoFarNode().run(
        incoming=json.dumps([{"id": "c", "composite": 0.5}]), current=best, context=context
    )
    assert improved is False and score == 3.0 and lower == best

    minimum, improved, score = await BestSoFarNode().run(
        incoming=json.dumps([{"id": "c", "composite": 0.5}, {"id": "d", "composite": 2.0}]),
        current=best,
        mode="minimize",
        context=context,
    )
    assert improved is True and score == 0.5

    tsv = tmp_path / "incoming.tsv"
    tsv.write_text("id\tcomposite\nc\t0.5\nd\t2.0\n", encoding="utf-8")
    from_tsv, improved, score = await BestSoFarNode().run(incoming=tsv, context=context)
    assert improved is True and score == 2.0

    with pytest.raises(ValueError, match="missing numeric field 'composite'"):
        await BestSoFarNode().run(incoming=json.dumps([{"id": "x"}]), context=context)
    assert "mode' must be one of" in str(BestSoFarNode.VALIDATE_INPUTS({"incoming": "[]", "mode": "both"}))


def _bedmethyl_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    bedmethyl = tmp_path / "mods.bed"
    bedmethyl.write_text(
        "\n".join(
            [
                "chrom\tstart\tend\tmod_code\tscore\tstrand\tthick_start\tthick_end\tcolor\tNvalid_cov\tpercent_modified",
                "chr1\t100\t101\tm\t500\t+\t100\t101\t255,0,0\t10\t80.0",
                "chr1\t200\t201\tm,CG,0\t200\t-\t200\t201\t255,0,0\t20\t50.0",
                "chr1\t500\t501\ta\t100\t+\t500\t501\t255,0,0\t30\t90.0",
                "chr1\t1500\t1501\tm\t100\t+\t1500\t1501\t255,0,0\t1\t20.0",
                "chr2\t50\t51\tm\t100\t+\t50\t51\t255,0,0\t5\t1000\t8\t4\t0\t0\t0\t0\t0",
                "chr3\t900\t901\tm\t100\t+\t900\t901\t255,0,0\t5\t60.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    transcript_bed = tmp_path / "tx.bed"
    transcript_bed.write_text(
        "chr1\t0\t1000\tTX1\tprotein_coding\nchr1\t1000\t2000\tTX2\tlncRNA\nchr2\t0\t100\tTX3\n",
        encoding="utf-8",
    )
    coverage = tmp_path / "cov.tsv"
    coverage.write_text("chrom\ttranscript\tmean_cov\nchr1\tTX1\t12.5\n", encoding="utf-8")
    return bedmethyl, transcript_bed, coverage


@pytest.mark.asyncio
async def test_bedmethyl_builder_aggregates_per_transcript(tmp_path: Path) -> None:
    bedmethyl, transcript_bed, coverage = _bedmethyl_fixture(tmp_path)
    context = _context(tmp_path)

    features, summary = await BedmethylFeatureBuilderNode().run(
        bedmethyl=bedmethyl,
        transcript_bed=transcript_bed,
        coverage_tsv=coverage,
        mod_codes="m",
        context=context,
    )
    rows: dict[str, dict[str, str]] = {}
    lines = Path(features).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    for line in lines[1:]:
        row = dict(zip(header, line.split("\t"), strict=True))
        rows[row["transcript_id"]] = row

    assert set(rows) == {"TX1", "TX2", "TX3"}
    tx1 = rows["TX1"]
    assert tx1["biotype"] == "protein_coding"
    assert tx1["n_sites"] == "2"
    assert tx1["n_covered_sites"] == "2"
    assert tx1["n_mod_sites"] == "2"
    assert float(tx1["mean_mod_fraction"]) == pytest.approx((10 * 0.8 + 20 * 0.5) / 30)
    assert float(tx1["mod_sites_per_kb"]) == pytest.approx(2.0)
    assert float(tx1["mean_coverage"]) == pytest.approx(15.0)
    assert tx1["length_bp"] == "1000"
    assert tx1["alignment_mean_cov"] == "12.5"

    tx2 = rows["TX2"]
    assert tx2["n_sites"] == "1"
    assert float(tx2["mean_mod_fraction"]) == pytest.approx(0.2)
    assert tx2["alignment_mean_cov"] == ""

    tx3 = rows["TX3"]
    assert float(tx3["mean_mod_fraction"]) == pytest.approx(1.0)
    assert rows["TX3"]["biotype"] == ""

    payload = json.loads(Path(summary).read_text(encoding="utf-8"))
    assert payload["n_transcripts"] == 3
    assert payload["n_sites_total"] == 6
    assert payload["n_sites_matched"] == 5
    assert payload["n_unassigned_sites"] == 1
    assert payload["mod_codes_used"] == ["m"]


@pytest.mark.asyncio
async def test_bedmethyl_builder_groups_by_chrom_and_scales_thousands(tmp_path: Path) -> None:
    bedmethyl, _, _ = _bedmethyl_fixture(tmp_path)
    context = _context(tmp_path)

    features, summary = await BedmethylFeatureBuilderNode().run(
        bedmethyl=bedmethyl, percent_scale="1000", context=context
    )
    lines = Path(features).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = {row["transcript_id"]: row for row in (dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:])}
    assert set(rows) == {"chr1", "chr2", "chr3"}
    assert float(rows["chr2"]["mean_mod_fraction"]) == pytest.approx(1.0)
    assert json.loads(Path(summary).read_text(encoding="utf-8"))["n_unassigned_sites"] == 0

    with pytest.raises(ValueError, match="at least 10"):
        short = tmp_path / "short.bed"
        short.write_text("chr1\t100\t101\n", encoding="utf-8")
        await BedmethylFeatureBuilderNode().run(bedmethyl=short, context=context)

    bad_bed = tmp_path / "bad.bed"
    bad_bed.write_text("chr1\t1\t1000\tTX\textra\nchr1\t5\t1\tTX2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tx_start >= tx_end"):
        await BedmethylFeatureBuilderNode().run(bedmethyl=bedmethyl, transcript_bed=bad_bed, context=context)


def _feature_table(tmp_path: Path, n_rows: int = 400, noise: float = 0.05, seed: int = 11) -> Path:
    rng = random.Random(seed)
    lines = ["id\tf1\tf2\ttarget"]
    for index in range(n_rows):
        f1 = rng.uniform(-3, 3)
        f2 = rng.uniform(-1, 1)
        target = 3.0 * f1 - 2.0 * f2 + 0.5 + rng.gauss(0, noise)
        lines.append(f"r{index}\t{f1:.5f}\t{f2:.5f}\t{target:.5f}")
    table = tmp_path / "features.tsv"
    table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return table


@pytest.mark.asyncio
@pytest.mark.parametrize("model_name", ["ridge", "boosted_stumps"])
async def test_predictor_train_learns_linear_relation(tmp_path: Path, model_name: str) -> None:
    table = _feature_table(tmp_path)
    context = _context(tmp_path)
    model, metrics, predictions = await SimplePredictorTrainNode().run(
        feature_table=table,
        target_column="target",
        model=model_name,
        n_stumps=120,
        context=context,
    )
    payload = json.loads(Path(metrics).read_text(encoding="utf-8"))
    assert payload["model"] == model_name
    assert payload["n"] == 400
    assert payload["n_train"] + payload["n_val"] == 400
    assert payload["train_r2"] > 0.9
    assert payload["val_r2"] > 0.9
    assert payload["train_rmse"] < 1.0 and payload["val_rmse"] < 1.0

    model_payload = json.loads(Path(model).read_text(encoding="utf-8"))
    assert model_payload["feature_names"] == ["f1", "f2"]
    if model_name == "boosted_stumps":
        assert 1 <= len(model_payload["stumps"]) <= 200
    lines = Path(predictions).read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t") == ["id", "target", "prediction", "split"]
    assert len(lines) == 401

    repeat = await SimplePredictorTrainNode().run(
        feature_table=table, target_column="target", model=model_name, n_stumps=120, context=context
    )
    assert Path(repeat[1]).read_text(encoding="utf-8") == Path(metrics).read_text(encoding="utf-8")

    scored_tsv, scored_json = await SimplePredictorScoreNode().run(
        model=model, feature_table=table, context=_context(tmp_path, "score")
    )
    scored_lines = Path(scored_tsv).read_text(encoding="utf-8").splitlines()
    assert scored_lines[0].split("\t") == ["id", "prediction"]
    assert len(scored_lines) == 401
    payload = json.loads(Path(scored_json).read_text(encoding="utf-8"))
    assert payload["model"] == model_name and len(payload["predictions"]) == 400


@pytest.mark.asyncio
async def test_predictor_train_k_fold_cross_validation(tmp_path: Path) -> None:
    table = _feature_table(tmp_path, n_rows=200)
    context = _context(tmp_path, "cv")
    model, metrics, predictions = await SimplePredictorTrainNode().run(
        feature_table=table,
        target_column="target",
        model="ridge",
        n_folds=5,
        seed=7,
        context=context,
    )
    payload = json.loads(Path(metrics).read_text(encoding="utf-8"))
    assert payload["n_folds"] == 5
    assert payload["val_r2"] > 0.9
    assert payload["val_r2_std"] is not None and payload["val_r2_std"] < 0.05
    assert payload["val_rmse"] < 1.0 and payload["val_rmse_std"] is not None
    assert payload["val_spearman"] > 0.95 and payload["val_spearman_std"] is not None
    assert len(payload["fold_val_r2"]) == 5
    assert len(payload["fold_val_rmse"]) == 5
    assert len(payload["fold_val_spearman"]) == 5
    assert all(value > 0.9 for value in payload["fold_val_r2"])
    assert payload["n_train"] == 200 and payload["n_val"] == 200

    lines = Path(predictions).read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t") == ["id", "target", "prediction", "split", "fold"]
    assert len(lines) == 201
    folds = {line.split("\t")[4] for line in lines[1:]}
    assert folds == {"0", "1", "2", "3", "4"}

    model_payload = json.loads(Path(model).read_text(encoding="utf-8"))
    assert model_payload["model"] == "ridge"

    repeat = await SimplePredictorTrainNode().run(
        feature_table=table, target_column="target", model="ridge", n_folds=5, seed=7,
        context=_context(tmp_path, "cv2"),
    )
    assert Path(repeat[1]).read_text(encoding="utf-8") == Path(metrics).read_text(encoding="utf-8")
    assert Path(repeat[2]).read_text(encoding="utf-8") == Path(predictions).read_text(encoding="utf-8")
    other_seed = await SimplePredictorTrainNode().run(
        feature_table=table, target_column="target", model="ridge", n_folds=5, seed=8,
        context=_context(tmp_path, "cv3"),
    )
    assert Path(other_seed[1]).read_text(encoding="utf-8") != Path(metrics).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_predictor_train_k_fold_rejects_more_folds_than_rows(tmp_path: Path) -> None:
    table = _feature_table(tmp_path, n_rows=4)
    with pytest.raises(ValueError, match="n_folds' must be smaller"):
        await SimplePredictorTrainNode().run(
            feature_table=table, target_column="target", n_folds=4, context=_context(tmp_path)
        )
    validation = SimplePredictorTrainNode.VALIDATE_INPUTS(
        {"feature_table": table, "target_column": "target", "n_folds": 1}
    )
    assert "n_folds' must be at least 0" not in str(validation)
    validation = SimplePredictorTrainNode.VALIDATE_INPUTS(
        {"feature_table": table, "target_column": "target", "n_folds": 101}
    )
    assert "n_folds' must be at most 100" in str(validation)


@pytest.mark.asyncio
async def test_predictor_rejects_missing_columns_and_params_out_of_bounds(tmp_path: Path) -> None:
    table = _feature_table(tmp_path, n_rows=20)
    context = _context(tmp_path)
    with pytest.raises(ValueError, match="must contain a 'missing' column"):
        await SimplePredictorTrainNode().run(
            feature_table=table, target_column="missing", context=context
        )
    with pytest.raises(ValueError, match="non-numeric value"):
        broken = tmp_path / "broken.tsv"
        broken.write_text("id\tf1\ttarget\nr0\talpha\t1.0\n", encoding="utf-8")
        await SimplePredictorTrainNode().run(feature_table=broken, target_column="target", context=context)

    validation = SimplePredictorTrainNode.VALIDATE_INPUTS(
        {"feature_table": table, "target_column": "target", "n_stumps": 500}
    )
    assert "n_stumps' must be at most 200" in str(validation)
    validation = SimplePredictorTrainNode.VALIDATE_INPUTS(
        {"feature_table": table, "target_column": "target", "val_fraction": 0.9}
    )
    assert "val_fraction' must be at most 0.5" in str(validation)

    model, _, _ = await SimplePredictorTrainNode().run(
        feature_table=table, target_column="target", context=context
    )
    trimmed = tmp_path / "trimmed.tsv"
    trimmed.write_text("id\tf1\nr0\t1.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing 1 model feature column"):
        await SimplePredictorScoreNode().run(model=model, feature_table=trimmed, context=context)


def test_path_or_inline_probes_survive_long_inline_payloads() -> None:
    from bionodulo.nodes.builtin.ml_design_family.adapter import load_json_or_table, read_sequence_text

    huge_json = json.dumps({"cds": "ATG" * 600})
    payload, table = load_json_or_table(huge_json, "candidates")
    assert table is None and payload["cds"].startswith("ATG")
    cds = "ATG" * 600
    assert read_sequence_text(cds, "cds") == cds


def test_rna_structure_validate_accepts_long_inline_sequence() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get("rnafold_mfe")
    assert node is not None
    long_sequence = "A" * 5000
    result = node.VALIDATE_INPUTS({"sequence": long_sequence})
    assert result is True


@pytest.mark.asyncio
async def test_scorer_uses_named_score_columns_and_skips_absent_objectives(tmp_path: Path) -> None:
    """Evaluator per-record tables carry semantic columns; missing/empty arms degrade fail-soft."""
    base = _base_cds()
    candidates = (
        await CandidateGeneratorNode().run(base_cds=base, n_candidates=8, seed=5, context=_context(tmp_path))
    )[0]
    entries = json.loads(Path(candidates).read_text(encoding="utf-8"))

    codon = tmp_path / "codon_per_record.tsv"
    codon.write_text(
        "id\tcai\tgc_window_max_dev\n"
        + "".join(f"{e['id']}\t{0.3 + 0.05 * i:.4f}\t{0.2 - 0.01 * i:.4f}\n" for i, e in enumerate(entries)),
        encoding="utf-8",
    )
    fold_missing = tmp_path / "fold_per_record.tsv"  # nonexistent path: skipped
    learned_empty = tmp_path / "predictions.tsv"
    learned_empty.write_text("id\tprediction\n", encoding="utf-8")  # header-only: skipped

    ranked, _ = await MultiObjectiveScorerNode().run(
        candidates=candidates,
        scores_1=codon,
        scores_2=fold_missing,
        scores_3=codon,
        scores_6=learned_empty,
        score_columns=json.dumps(
            {"scores_1": "cai", "scores_3": "gc_window_max_dev", "scores_6": "prediction"}
        ),
        modes=json.dumps({"scores_3": "minimize"}),
        weights=json.dumps({"scores_1": 2.0, "scores_3": 1.0}),
        context=_context(tmp_path, "cols"),
    )
    payload = json.loads(Path(ranked).read_text(encoding="utf-8"))
    assert len(payload) == 8
    assert all(set(entry["per_objective"]) == {"scores_1", "scores_3"} for entry in payload)
    composites = [entry["composite"] for entry in payload]
    assert composites == sorted(composites, reverse=True)
    assert len({round(entry["composite"], 9) for entry in payload}) == len(payload)


@pytest.mark.asyncio
async def test_scorer_derives_candidate_ids_without_candidates_input(tmp_path: Path) -> None:
    scores = tmp_path / "scores.tsv"
    scores.write_text(
        "id\tcai\nb\t0.9\na\t0.1\nc\t0.5\n",
        encoding="utf-8",
    )
    ranked, _ = await MultiObjectiveScorerNode().run(
        scores_1=scores,
        score_columns=json.dumps({"scores_1": "cai"}),
        context=_context(tmp_path, "nocand"),
    )
    payload = json.loads(Path(ranked).read_text(encoding="utf-8"))
    assert [entry["id"] for entry in payload] == ["b", "c", "a"]


@pytest.mark.asyncio
async def test_predictor_score_empty_model_returns_empty_predictions(tmp_path: Path) -> None:
    table = _feature_table(tmp_path, n_rows=10)
    node = SimplePredictorScoreNode()
    tsv_path, json_path = await node.run(model="", feature_table=table, context=_context(tmp_path))
    lines = Path(tsv_path).read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t") == ["id", "prediction"]
    assert len(lines) == 1
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert payload == {"model": None, "predictions": []}
    assert SimplePredictorScoreNode.VALIDATE_INPUTS({"model": "", "feature_table": table}) is True


def test_codon_metrics_accepts_rna_uracil(tmp_path):
    """The OpenVaccine leg feeds RNA molecules (U for T) into codon metrics;
    the first live execution failed closed on the uracil. Metrics must
    normalise U to T instead of rejecting the panel."""
    import asyncio
    import json
    from pathlib import Path
    from types import SimpleNamespace

    from bionodulo.nodes.builtin.codon_design_family.codon_metrics import CodonMetricsNode

    fasta = tmp_path / "panel.fa"
    fasta.write_text(">mol_1\nAUGAAACCCGGGUUU\n", encoding="utf-8")
    node = CodonMetricsNode()
    ctx = SimpleNamespace(node_dir=str(tmp_path / "out"))
    result = asyncio.run(node.run(context=ctx, cds=str(fasta), window=5))
    assert result, "metrics must produce outputs for an RNA panel"
