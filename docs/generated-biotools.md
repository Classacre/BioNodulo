# Generated executable bio.tools integrations

`python -m bionodulo.nodes.generate_registry` joins **every tracked CWL
descriptor** in a pinned GitHub repository to a hash-verified bio.tools snapshot.
The source descriptor must explicitly associate a SoftwareRequirement package
with a bio.tools accession. Display names and package-name similarity are not
identity evidence. No per-tool Python adapter, alias table, or hand-maintained
list is involved in this path.

The generator retains a coverage ledger for all scanned descriptions, including
unsupported features, missing identities, unavailable exact package versions,
installation failures, and candidates outside an explicit processing budget.
The registry's total record count remains a separate denominator: scanning one
upstream source does not establish executable coverage of all bio.tools records.

## Execution architecture

An admitted descriptor becomes a data-only `NodeSpec.cwl_reference` containing
the unchanged source text, source hash, source URL pinned to a Git commit,
bio.tools accession, normalized inputs/outputs, and engine version. A single
`CwlReferenceNode` adapter delegates CWL command construction and expressions to
the reference engine. Dependencies are solved from exact upstream package pins
using micromamba, then represented by the complete installed Conda artifact lock.
Packages are not silently renamed or upgraded to make an upstream description
work.

The shared CWL engine runs separately from each tool's Conda environment. This
allows tools with incompatible Python requirements to use one engine. Engine
version and executable hashes are recorded and optional configured hash
expectations are checked. This is not a byte-level lock of every Python and
system library used by the engine. JavaScript uses an explicitly configured
Node.js executable. Tool execution uses the selected package prefix; readiness
checks do not substitute unrelated programs from the host PATH.

Each attempt stages copies of input files and directory trees, writes the retained
descriptor and job, runs in a private output directory, and publishes validated
File and Directory outputs with byte hashes and directory inventories. Publication rejects symlinks and paths outside the
engine's private output directory. Input File `format` and `secondaryFiles`
metadata can be supplied explicitly. Literal CWL secondary-file suffix/caret
rules stage only the declared companions; dynamic rules require explicit
secondary-file objects. Required missing companions fail before execution.
Generated output values currently expose paths; rich File metadata
is retained in the engine result rather than propagated as a typed CWL File
object across every BioNodulo edge.

## Current profile boundary

The reference profile accepts self-contained CWL CommandLineTool documents and
projects scalar, enum, primitive-array, File and Directory inputs. Records and
supported input unions use JSON controls and retain their original structure for
the reference engine to validate. Explicit nested CWL File and Directory objects
are copied into private staging; strings inside records are not guessed to be
paths. Artifact outputs can be File, Directory, arrays of either, or a union of
one artifact kind and its array form. Scalar and record outputs still require a
value-output contract and are not admitted as file paths. The engine performs
CWL validation in addition to BioNodulo's admission checks.

ShellCommandRequirement delegates shell semantics to cwltool and the native
`/bin/sh`; the resolved shell path and hash are recorded. An optional
`BIONODULO_CWL_SHELL_SHA256` enforces an expected shell hash. Required Docker,
network, resource and other unsupported requirements are rejected.
Optional Docker/resource hints are recorded as unfulfilled where the
native backend does not enforce them. Optional top-level HTTPS `$schemas` links
are retained but not fetched (`--skip-schemas`); CWL syntax validation remains
enabled. Imports/includes and unsupported schemas are not silently rewritten.
This native backend is not a container sandbox and does not establish container
equivalence or scientific validity.

Every newly generated native environment includes the execution profile's
`coreutils==9.5` utility baseline. A program can be a shell launcher even when its
CWL does not request shell command rendering. Keeping the baseline inside the
locked prefix avoids reliance on unspecified host utilities. Coverage receipts
separate upstream software requirements from these profile requirements;
conflicting upstream pins are rejected rather than replaced.

## Generate and run

Use a clean checkout with raw bytes matching the pinned Git revision. Windows
Git line-ending conversion can change those bytes; a native Linux checkout with
`core.autocrlf=false` avoids that ambiguity.

```sh
python -m bionodulo.nodes.generate_registry \
  --repository /path/to/upstream-checkout \
  --revision FULL_GIT_COMMIT \
  --source-url https://github.com/OWNER/REPOSITORY \
  --snapshot /path/to/registry.jsonl \
  --manifest /path/to/manifest.json \
  --output /path/to/generated
```

Scanning does not execute a tool. Add `--realize --prefix-root /fresh/prefix/root
--micromamba /absolute/micromamba --cwltool /absolute/cwltool` to install exact
requirements and generate a catalog. `--limit N` applies a deterministic
round-robin over sorted accessions, then sorted descriptor paths. The default
zero limit processes all eligible descriptions. Selection and failures are
retained, so the successful subset cannot replace the original denominator.

Primitive CWL outputs (`string`, `int`/`long`, `float`/`double`, and `boolean`)
are published as UTF-8 JSON files on `artifact.file` ports. Each file contains
the exact JSON primitive and a trailing newline. The source CWL type is retained
in the output mapping and publication receipt. This is an explicit artifact
projection for the current graph contract; consumers must parse the JSON file
to obtain the primitive value. Unsupported record outputs are still rejected.

To regenerate contracts from completed installations without installing anything,
use `--realize --no-install --receipts-from /previous/generated` and a new
`--output`. Existing prefixes are located from their retained receipts because
Conda environments may contain nonrelocatable paths. Every reused prefix is verified again;
missing or incomplete receipts stay `environment_unavailable`. This separates
dependency acquisition from contract generation and makes importer corrections
testable without manually reconstructing package locks.
Omit `--no-install` and provide `--micromamba` plus a fresh `--prefix-root` to
reuse verified environments while acquiring newly eligible dependency groups.
Verified installed pins do not depend on a new network availability check;
missing groups still undergo exact-version acquisition without guessed aliases.
`--recover-incomplete` can reverify installed prefixes left by interrupted or
failed realization. It requires an exact reservation marker and retained solver
logs, then runs the complete lock and installed-file checks before publishing
a receipt. It can be combined with `--no-install` and an explicit `--micromamba`
for lock inspection; failed integrity checks remain failures.
The new output also retains the prior coverage, availability/run, and environment
receipts in `acquisition-evidence`, with a byte-hash manifest referenced by the
new run. Run records remain `in_progress` after interruption and gain a completion
timestamp only after generation finishes normally.

Configure the app and queue workers with:

```sh
export BIONODULO_DECLARATIVE_CATALOG=/path/to/generated/catalog.json
export BIONODULO_CWL_ENVIRONMENTS="$(cat /path/to/generated/prefixes.json)"
export BIONODULO_CWLTOOL=/absolute/cwltool
export BIONODULO_CWL_NODEJS=/absolute/engine-bin/node
export BIONODULO_ALLOW_UNVERIFIED_CWL=1
```

The opt-in makes the experimental boundary explicit. It does not grant release
maturity or scientific verification. Optional `BIONODULO_CWLTOOL_SHA256` and
`BIONODULO_CWL_NODEJS_SHA256` values are `sha256:`-prefixed expected hashes.
Use a native Linux workspace. Generated nodes appear in object discovery and
the bio.tools browser automatically through their exact accession, without
editing the registry snapshot's curated links.

## Evidence and tests

The opt-in `tests/test_generated_biotools_end_to_end.py` loads an actual generated
catalog, checks discovery/readiness, submits real jobs through the app API queue,
checks independent fixture outputs, verifies input immutability, and exports
RO-Crate provenance. No subprocess or result is mocked. A missing generated
runtime is a skipped fixture case and remains a generation failure in the
coverage ledger; it is never counted as an execution pass.

```sh
export BIONODULO_GENERATED_E2E_ROOT=/path/to/generated
export BIONODULO_GENERATED_E2E_CASES=/path/to/fixtures/cases.json
export BIONODULO_GENERATED_E2E_EVIDENCE=/path/to/evidence
python -m pytest tests/test_generated_biotools_end_to_end.py -q
```

Scientific fixture cases are authored separately from integration generation.
They can establish the specified behavior on the provided small data, not
universal correctness, every option combination, research novelty, or PhD
completion. Upstream jobs with missing data are recorded as unavailable; their
existence alone is not evidence of successful testing.

## Registry-wide source discovery

The executable catalog above and the complete bio.tools registry have different
denominators. The source-discovery CLI accounts for every record in a verified
registry snapshot without registering any new executable nodes:

```sh
python -m bionodulo.nodes.discover_registry \
  --snapshot /path/to/verified/registry.jsonl \
  --manifest /path/to/verified/manifest.json \
  --output /path/to/registry-discovery \
  --iuc-repository /path/to/pinned/tools-iuc \
  --iuc-revision FULL_GIT_COMMIT \
  --parse-iuc-official \
  --iuc-staging /native/private/staging-root
```

`registry-discovery.jsonl` contains exactly one row per bio.tools accession.
It inventories typed CWL and Galaxy wrapper links, API and command-line
specifications, explicitly typed repositories, and package-registry identities.
Display names and package-name similarity are never joins. Each row keeps its
source candidates and concrete gaps, including `not_execution_admitted`.
`summary.json` reports record counts separately from candidate counts because
one record can contain several source links and formats.

When a pinned Galaxy IUC repository is supplied, exact record URLs that name a
`galaxyproject/tools-iuc` path or ToolShed owner `iuc` can be joined to the
pinned Git-tree inventory. Git object IDs remain available even for a partial
clone whose blobs cannot be materialized on the host. Galaxy XML is not
interpreted with custom XML or template logic. With `--parse-iuc-official`, the
CLI stages byte-verified blobs from the pinned Git revision and uses the official
`galaxy-tool-util` parser for macro expansion, typed inputs and outputs, tests,
requirements, and explicit bio.tools xrefs. `galaxy-iuc-parser.jsonl` retains the
source and imported macro byte hashes for each successful parse; parser errors
and incomplete source closures stay in the same ledger. Official parser
classification separates parsed tool wrappers, tool sources with IDs that fail
model parsing, XML without tool IDs, and XML the source loader cannot classify;
supporting macro/config XML is not mislabeled as a failed tool. The separate
`galaxy-iuc-xref-joins.jsonl` records exact xref joins to the verified registry.
Its summary records the parser distribution and version. These artifacts remain
discovery evidence: repository discovery and successful parsing do not prove
installability, app execution, or scientific validity, and Galaxy wrappers are
not registered until a runtime adapter exists. Test-data files, data-table
configuration, loc files, and referenced databases are separate runtime closure
requirements and remain an explicit gap in every parsed wrapper record.
