# Script map

Run these commands from the repository root with the project Python environment.
Use `--help` on a script with a command-line parser for its full options. Some
scripts write generated files or reports, so review the command's inputs and
output directory before running it.

| Task | Script or command | Notes |
| --- | --- | --- |
| Refresh bio.tools discovery metadata | `python scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/current --workers 2` | Fresh, verified snapshot; see [registry sync guide](../reports/biotools_registry/SYNC.md). |
| Compare registry records with app nodes | `python scripts/audit_biotools_coverage.py --snapshot-dir reports/biotools_registry/current --output-dir reports/biotools_registry/current/coverage --check-imports` | Produces a gap ledger and discovery JSON in the audit output directory. |
| Curate registry links and inferred contracts | `link_biotools.py`, `infer_contracts.py`, `acquire_typed_cwl_links.py` | Research and curation tools; inspect their inputs before writing evidence. |
| Generate and verify registry toolbox | `generate_registry_toolbox.py`, `verify_registry_toolbox.py`, `probe_registry_toolbox_api.py` | See [generated toolbox guide](../docs/GENERATED_REGISTRY_TOOLBOX.md). |
| Build or check the typed catalog | `build_catalog_ledger.py`, `compile_catalog.py`, `audit_generated_catalog.py` | Catalog generation and validation. |
| Refresh node discovery files | `gen_node_index.py`, `export_capabilities.py` | Called by `make catalog`. |
| Check node and environment conformance | `node_linter.py`, `smoke_harness.py`, `audit_template_environment_locks.py`, `solve_env_lock.py`, `solve_macos_locks.py` | The smoke harness and lock solvers may invoke external tools. |
| Refresh template layout and thumbnails | `python scripts/relayout_templates.py --dry-run` then `python scripts/relayout_templates.py <template.json>` | The second command writes the template JSON and its PNG thumbnail. |
| Check source and migration evidence | `node_migration_ledger_validation.py`, `audit_oci_reference_coverage.py`, `run_oci_ucsc_oracle.py` | `node_source_identity.py` and `oci_twobit_oracle.py` are support modules for these checks. |
| Run thesis demonstrations and evaluation | `run_contract_demo.py`, `execute_contract_chain.py`, `roundtrip_fidelity.py`, `evaluation/agent_arm.py`, `evaluation/adjudicate.py` | Read each script's docstring for fixture and output requirements. |
| Maintain release and type checks | `set_version.py`, `mypy_ratchet.py` | `mypy_ratchet.py` runs in CI. |

The former `crawl_biotools_registry.py` was a resumable crawler that could keep
stale metadata. It was retired in favor of `sync_biotools_registry.py`; the
existing `reports/biotools_registry/completeness_report.json` and
`inference_agreement.json` remain historical evidence, not current registry
coverage or scientific validation. The former `replace_html_reports.py` was a
completed template migration. The `html_report` node itself remains available.
