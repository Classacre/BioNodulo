# Builtin expansion verification — 2026-09-29

This follow-up supersedes the release-blocker snapshot in
[the earlier handoff audit](../HANDOFF-VERIFICATION-2026-09-29.md). It describes
the candidate on `feat/tool-knowledge-graph` / PR #13, not the deployed website.
Node counts measure operations, not distinct bio.tools records.

## Scope

The catalog contains **1,370 builtins**, up from 983: **387 additions**, comprising
373 generated operations and 14 separately implemented operations.

| Family | Added operations |
| --- | ---: |
| CSVtk | 47 |
| EMBOSS | 169 |
| HTSlib BGZip/Tabix | 4 |
| SeqFu | 23 |
| SeqKit | 31 |
| TaxonKit | 8 |
| UniKmer | 23 |
| vcflib | 82 |

`vcflib_bgziptabix` was withdrawn because its concatenated shell-wrapper help did
not establish an honest execution/output contract. Separate BGZip and Tabix
nodes remain. Existing failed receipts remain as historical evidence.
`csvtk_version` was also withdrawn: the pinned binary ignored the generated
output-file argument, printed its version to stdout and created no advertised
artifact. Its former required table input was also inapplicable to that command.

## Repairs made during verification

- Expose all required EMBOSS file ports, including both alignment inputs.
- Parse split-bracket ACD blocks correctly: `inforesidue` now has its description,
  required residue code, real output file and ontology metadata. Newly parseable
  programs awaiting review are explicitly excluded from generation.
- Preserve computed EMBOSS defaults as unspecified; do not invent zero values.
  Explicit boolean inputs pass `Y` or `N`, including disabling default-on flags.
- Correct SeqFu paired inputs, directory inputs/outputs, subtract's two files,
  mixed-case flags, and descriptions; correct SeqKit pair/split output shapes.
- Make UniKmer directory outputs use the executor-assigned directory and require
  actual files. `grep` supplies an explicit output prefix to prevent stdout-only
  success with an empty advertised directory.
- Remove the captured container-only TaxonKit default `/root/.taxonkit` from UI
  metadata. Explicit user-selected data directories still render normally.
- Replace captured help banners with source-backed descriptions. Every addition
  has a nonempty description and exportable citation metadata. UniKmer uses an
  official software-repository citation, with no invented publication or DOI.
- Regenerate index, editor metadata, capabilities and catalog projections; make
  manifest checking fail on missing families and empty verification sets.

## Validation and limits

| Gate | Result |
| --- | --- |
| Index, editor metadata, capabilities, compiled catalog | Consistent at 1,370 nodes; all generation checks pass |
| Generated manifests | 373/373 contracts match |
| Added-node command linter | All 387 inspected; zero findings |
| Offline regeneration from the retained bundle | All 373 modules and seven manifests reproduce byte for byte |
| Frontend unit suite | 654 tests in 135 files pass |
| Editor census and Tool Atlas | All 387 additions exercised; all 12 scenarios pass across the final run and cold-start rerun |
| Python suite | 9,072 unique tests pass across the full run and export rerun; 652 skipped |
| Frontend lint and production build | Pass; 36 pre-existing lint warnings and bundle-size warnings remain |
| Python Ruff | Pass across `bionodulo` and `tests` |
| Mypy 2.1.0, Python 3.11/Linux target | 529 existing diagnostics in 197 files; matches the unchanged baseline |
| Fresh eight-family container sample | 14 executions, 28/28 retained oracle checks pass |
| Staged fixture and receipt byte preservation | 524 files match their working-tree bytes exactly |
| Staged secret scan | Gitleaks 8.30.1 with repository rules: no leaks found |

The full Python run returned 9,065 passes, 652 skips and seven failures. All seven
were CWL subprocess imports from an isolated environment where the project had
not been installed. After installing this checkout editable, all 31 tests in
`tests/test_workflow_export.py` passed, including those seven. No application
change was needed for that environment repair. Earlier missing Biopython/POD5
dependencies and a regeneration race were resolved before the final full run.

The final browser census returned ten passes and two cold-start setup timeouts;
both timed-out families passed on rerun. The suite now budgets cold startup and
scales its family timeout with the census size. Twenty representative
[properties-panel and canvas screenshots](ui-2026-09-29/) are retained; examples
from all eight families were visually inspected, including paired inputs,
computed defaults, long parameter lists and software citations.

The new Playwright suite reads real shipped metadata and exercises every added
node's library search, insertion, title, properties, required-input presentation
and removal. It also captures representative panels and canvas nodes. Host APIs
are stubbed: this verifies editor behavior, not backend execution. Tool Atlas
tests exercise the complete catalog, relationship explanations, insertion,
references, export, keyboard navigation and narrow-screen layout.

[Fourteen fresh digest-pinned container runs](../run-receipts/release-2026-09-29/README.md)
span all eight added families. The retained oracle checks artifact hashes and
expected content (28 checks), including actual paired FASTQ reads, decoded k-mer
sets, a tiny taxonomy, tabular projection, VCF records and 12/12-base alignments.
Both default EMBOSS water and explicit `brief=false` were executed.

These are bounded fixtures and command-contract runs. They do **not** establish
execution of every new node, every parameter combination, the cloud queue,
production deployment, all bio.tools coverage, or completion of the PhD scope.
The typed release/promotion gates remain distinct from importable builtin counts.

## Publication hygiene

Small test fixtures and receipt outputs are retained so receipt oracles can run
after cloning. Historical receipt command lines may contain the original Windows
checkout path; tests resolve their retained artifacts relative to the repository.
The new sample also retains explicit failure boundaries rather than treating
exit code zero as proof of a correct output.

Large reproducible discovery reports remain local and ignored. Their scripts,
findings and provenance remain in version control. They were not deleted.
The [generation guide](GENERATION.md) includes a compact, hash-pinned capture
archive and exact regeneration commands; all 373 emitted modules and all seven
manifests reproduce byte for byte from those retained inputs.

| Local output | Bytes | SHA-256 |
| --- | ---: | --- |
| `reports/node-expansion/gap-candidates.json` | 24462607 | `1b0370ea4d8f6bcf1459e585f04f999b23b411a8b3e3d921232f4bb4e10170b0` |
| `reports/galaxy-ingestion/conversion.json` | 9772203 | `c71ee1323a7bf17f8c90e738968c2411395e24eebd0f49794e28344dcc1f9c08` |
| `reports/galaxy-ingestion/wrapper-analysis.json` | 6097704 | `8c0d38ac1cb4c7d19f265b79bd0b314726f9c197c0a8e1a1936b44e29ac5c759` |
