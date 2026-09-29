# Reports

These are retained measurements and reproducible examples, not a declaration
that every registry entry can execute. Read each report's date, input snapshot
and validation boundary before quoting a result.

| Location | Contents |
| --- | --- |
| [Builtin release verification, 2026-09-29](node-expansion/RELEASE-VERIFICATION-2026-09-29.md) | 387 additions, repaired generated contracts, editor coverage, bounded real execution evidence and explicit release limits |
| [Handoff verification, 2026-09-29](HANDOFF-VERIFICATION-2026-09-29.md) | Independent cleanup and node-expansion audit, repaired regressions, retained test evidence and remaining release blockers |
| Registry toolbox | [Snapshot manifest](registry-toolbox/snapshot-manifest.json), [definition coverage](registry-toolbox/coverage.json), [API coverage](registry-toolbox/api-coverage.json) and [typed-CWL acquisition](registry-toolbox/typed-cwl-acquisition.json); see the [toolbox guide](../docs/GENERATED_REGISTRY_TOOLBOX.md) |
| [biotools_registry](biotools_registry/README.md) | Historical annotation/contract reports and current synchronization instructions |
| [biotools_registry/BUILTIN-EXPANSION-2026-09-25.md](biotools_registry/BUILTIN-EXPANSION-2026-09-25.md) | Dated census, per-accession ledger and verified-operation report for all 34,248 bio.tools records. Read its numerator/denominator pairs and stated gaps before quoting any count |
| [run-receipts](run-receipts/) | Retained executor and container runs with differing evidence scopes. Some include artifact hashes and [independent protein-workflow checks](../tests/nodes/protein_database/test_receipt_oracle.py); sampled container success is not queue or scientific coverage for the whole catalog |
| [galaxy-ingestion](galaxy-ingestion/GALAXY-INGESTION-FINDINGS.md) | Measured census of importing Galaxy's tool wrappers. Read before scoping any "match Galaxy's tool count" work: the tier breakdown explains why a wrapper count is not an executable count |
| [node-expansion](node-expansion/EMBOSS-EXPANSION-FINDINGS.md) | How 166 EMBOSS nodes were generated from the suite's own ACD parameter definitions, the six generator bugs found, and the measured 76.3% run rate of an 80-node sample |
| [node-expansion](node-expansion/SUBCOMMAND-EXPANSION-FINDINGS.md) | The same method applied to subcommand CLIs: 50 csvtk nodes from cobra `--help` tables, and why cobra's silence on required flags forces an empirical probe |
| [oci-reference](oci-reference/README.md) | Experimental container-profile resolution, execution, cancellation and timeout evidence |
| [contract_demo](contract_demo/) | Deterministic contract-chain fixture and example RO-Crate; reproduced by `scripts/run_contract_demo.py` |
| [roundtrip_fidelity](roundtrip_fidelity/fidelity.md) | Workflow-format round-trip measurements; reproduced by `scripts/roundtrip_fidelity.py` |
| [adaptability-note.md](adaptability-note.md) | Scope and limitations of the RNA-seq structural compatibility tests |

Keep raw registry downloads in ignored snapshot directories. Put ad-hoc logs,
screenshots and local QA output under ignored `artifacts/` instead of adding
another report tree. Retain a report when it supports a reproducible test,
release decision or measured scientific claim.
