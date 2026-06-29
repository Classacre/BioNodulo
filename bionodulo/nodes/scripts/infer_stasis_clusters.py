#!/usr/bin/env python3
"""Infer stasis clusters from HyPhy B-STILL JSON results."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import hypergeom


def get_sf_optimized(n: int, d: int, gene_length: int, stasis_sites: int, cache: dict[tuple[int, int], float]) -> float:
    """Return a cached hypergeometric survival-function value."""
    key = (n, d)
    if key not in cache:
        cache[key] = float(hypergeom.sf(n - 1, gene_length, stasis_sites, d))
    return cache[key]


def scan_intervals(
    indices: list[int] | np.ndarray,
    gene_length: int,
    stasis_sites: int,
    max_size: int,
    sf_cache: dict[tuple[int, int], float],
    threshold: float | None = None,
) -> float | list[dict[str, Any]]:
    """Scan intervals anchored by stasis events."""
    best_p = 1.0
    segments: list[dict[str, Any]] = []
    num_events = len(indices)

    for n in range(3, min(max_size + 1, num_events + 1)):
        for i in range(num_events - n + 1):
            d = int(indices[i + n - 1]) - int(indices[i]) + 1
            p = get_sf_optimized(n, d, gene_length, stasis_sites, sf_cache)

            if threshold is None:
                if p < best_p:
                    best_p = p
            elif p <= threshold:
                segments.append(
                    {
                        "start": int(indices[i] + 1),
                        "end": int(indices[i + n - 1] + 1),
                        "p_value": p,
                        "k": n,
                        "d": int(d),
                    }
                )

    return best_p if threshold is None else segments


def merge_segments(segments: list[dict[str, Any]], merge_dist: int = 15) -> list[dict[str, Any]]:
    """Merge overlapping or nearby significant segments."""
    if not segments:
        return []
    segments.sort(key=lambda segment: segment["start"])

    merged = []
    curr = segments[0]
    for next_segment in segments[1:]:
        if next_segment["start"] <= curr["end"] + merge_dist:
            curr["end"] = max(curr["end"], next_segment["end"])
            curr["p_value"] = min(curr["p_value"], next_segment["p_value"])
            curr["d"] = curr["end"] - curr["start"] + 1
        else:
            merged.append(curr)
            curr = next_segment
    merged.append(curr)
    return merged


def infer_stasis_clusters(args: argparse.Namespace) -> None:
    """Run the Galaxy B-STILL cluster inference workflow."""
    try:
        with Path(args.input).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        print(f"Error loading JSON: {exc}")
        sys.exit(1)

    sites = data.get("MLE", {}).get("content", {}).get("0", [])
    ebfs = [site[12] if len(site) > 12 and isinstance(site[12], (int, float)) else 0 for site in sites]
    gene_length = len(ebfs)

    if gene_length < 10:
        print("Alignment too short for cluster analysis.")
        sys.exit(0)

    stasis_indices = np.array([i for i, value in enumerate(ebfs) if value >= args.ebf])
    stasis_sites = len(stasis_indices)

    print("--- B-STILL Cluster Inference ---")
    print(f"Input: {args.input}")
    print(f"Gene Length (L): {gene_length} codons")
    print(f"Stasis Sites (K): {stasis_sites} (EBF >= {args.ebf})")

    if stasis_sites < 3:
        print("Insufficient stasis sites to form clusters (minimum 3 required).")
        sys.exit(0)

    print(f"Running {args.permutations} permutations for FWER control...")
    null_min_ps = []
    all_positions = np.arange(gene_length)
    sf_cache: dict[tuple[int, int], float] = {}

    start_time = time.time()
    for i in range(args.permutations):
        if i > 0 and i % 1000 == 0:
            elapsed = time.time() - start_time
            print(f"  Processed {i} permutations... ({i / elapsed:.1f} per sec)")
        shuffled = sorted(np.random.choice(all_positions, stasis_sites, replace=False))
        min_p = scan_intervals(shuffled, gene_length, stasis_sites, args.max_cluster, sf_cache)
        null_min_ps.append(min_p)

    crit_p = float(np.percentile(null_min_ps, args.alpha * 100))
    print(f"Gene-specific Critical P-value (FWER {args.alpha}): {crit_p:.2e}")

    print("Scanning observed sequence for significant clusters...")
    raw_segments = scan_intervals(
        stasis_indices,
        gene_length,
        stasis_sites,
        args.max_cluster,
        sf_cache,
        threshold=crit_p,
    )

    final_clusters = merge_segments(raw_segments, merge_dist=args.merge)

    for cluster in final_clusters:
        cluster["k"] = sum(1 for idx in stasis_indices if cluster["start"] <= idx + 1 <= cluster["end"])

    print(f"\nFound {len(final_clusters)} significant stasis clusters:")
    if final_clusters:
        print("\nLegend:")
        print("  k : Number of high-confidence stasis sites within the cluster")
        print("  d : Total span of the cluster in codons")
        print("\n{:<8} | {:<8} | {:<5} | {:<5} | {:<10}".format("Start", "End", "k", "d", "P-value"))
        print("-" * 45)
        for cluster in final_clusters:
            print(
                "{:<8} | {:<8} | {:<5} | {:<5} | {:.2e}".format(
                    cluster["start"],
                    cluster["end"],
                    cluster["k"],
                    cluster["d"],
                    cluster["p_value"],
                )
            )

    if args.output:
        output_data = {
            "input_file": args.input,
            "parameters": vars(args),
            "summary": {
                "gene_length": gene_length,
                "total_stasis_sites": stasis_sites,
                "critical_p_value": crit_p,
                "num_clusters": len(final_clusters),
            },
            "clusters": final_clusters,
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output_data, indent=4) + "\n", encoding="utf-8")
        print(f"\nDetailed results saved to {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Infer stasis clusters from B-STILL JSON.")
    parser.add_argument("input", help="Path to B-STILL JSON result file")
    parser.add_argument("--ebf", type=float, default=10.0, help="EBF threshold for defining stasis sites")
    parser.add_argument("--permutations", type=int, default=10000, help="Permutations for FWER control")
    parser.add_argument("--alpha", type=float, default=0.05, help="Family-wise error rate threshold")
    parser.add_argument("--max-cluster", type=int, default=30, help="Maximum number of stasis sites per interval scan")
    parser.add_argument("--merge", type=int, default=15, help="Distance in codons to merge adjacent clusters")
    parser.add_argument("--output", help="Path to save results in JSON format")
    return parser


def main() -> None:
    infer_stasis_clusters(build_parser().parse_args())


if __name__ == "__main__":
    main()
