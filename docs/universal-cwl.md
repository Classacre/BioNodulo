# Descriptor-driven tool integration: first native profile

BioNodulo can now import a supported upstream CWL `CommandLineTool` into the existing typed `NodeSpec`, compile it, expose its ports and controls through `/api/object_info`, and execute it through the ordinary workflow queue. Every imported tool uses `bionodulo.nodes.declarative_cwl`; adding one requires descriptor/catalog data, not a new Python tool class or static-index edit.

This native profile supports a bounded subset of CWL. Broader descriptor execution uses the separate [CWL reference-engine profile](generated-biotools.md). See [tool integration](tool-integration.md) for the shared design, current profiles and remaining validation work.

## Import and run

Provide an existing, genuinely locked `EnvironmentSpec` JSON, including executable probes with exact versions and binary fingerprints. The importer does not install the environment or manufacture verification evidence.

```sh
python -m bionodulo.nodes.import_cwl tool.cwl \
  --environment environment.json \
  --node-id imported_tool --tool-id upstream_package --tool-version 1.2.3 \
  --source-uri https://example.org/pinned-revision/tool.cwl \
  --output generated-catalog.json
```

Use `--append` to add another descriptor. Duplicate IDs, duplicate YAML keys and unsupported descriptor features fail explicitly. The output is a data-only catalog containing typed specifications. The existing compiler validates it; no tool-specific source file is emitted. The CLI retains the original source bytes' SHA-256 and size separately from the canonical parsed descriptor digest.

Configure the app and any local execution worker with the same catalog and realized environment mapping:

```sh
export BIONODULO_DECLARATIVE_CATALOG=/absolute/path/generated-catalog.json
export BIONODULO_CWL_ENVIRONMENTS='{"environment-id-from-lock":"/absolute/environment/prefix"}'
export BIONODULO_ALLOW_UNVERIFIED_CWL=1
```

The last setting explicitly permits experimental candidates. Imported nodes retain `experimental=true` and `verification=unverified`; the setting creates no release or scientific validation evidence. Catalog loading is atomic and rejects collisions with builtins. Restart the app after changing the catalog. Environment locators such as `bin/tool` resolve inside the configured prefix; the shared adapter does not fall back to an arbitrary executable on PATH.

The normal Run readiness check verifies the configured declarative runtime independently of the legacy Pixi environment. A workflow made entirely of imported CWL nodes may report `execution_ready=true` while `env_ready=false`; the latter still describes the legacy environment. Mixed workflows must also satisfy their legacy runtime requirements. Missing or mismatched declared executables block admission and are checked again during execution.

Use a native Linux workspace filesystem for this profile. The existing stdout output collector requires anonymous temporary files and safe publication (`O_TMPFILE`/`linkat`); the tested WSL Windows mount under `/mnt/d` does not provide this. A native Linux directory such as `/opt/bionodulo-phd/universal-preview` worked in the audit. The filesystem restriction remains a compatibility gap, not a successful Windows-mount execution claim.

## Supported profile and boundaries

The first profile uses CWL v1.2 command tools and native Linux execution. This audit ran on amd64; host checks recognize arm64, but arm64 execution is not proven here. It supports map/list input declarations, scalar File/string/int/float/boolean inputs, optional inputs, scalar defaults, explicit unique nonnegative argument positions, separated prefixes, literal positioned arguments, and one required File output at an exact relative path or stdout. Unbound inputs remain inputs without becoming command arguments. Empty output files are valid. Source and contract digests travel with the invocation.

Unsupported constructs are rejected: workflows, JavaScript/expressions, shell requirements, arrays/records, secondary files, directory ports, stdin/stderr declarations, arbitrary requirements/hints, container execution, File defaults, optional/multiple/pattern outputs, tied positions, and non-separated prefixes. The parser is deliberately narrower than the full CWL standard. The existing stdout collector currently limits imported stdout artifacts to **1 MiB**; larger scientific streams require a streaming collector extension. This limit does not apply to exact files produced directly by the tool.

The runner verifies the configured executable's version and mandatory fingerprint, stages File inputs as independent read-only copies, preserves binary stdout, and collects declared outputs through the existing output-contract machinery. Each attempt uses a fresh private workspace, so a previous output cannot satisfy a new invocation. Binary capture refuses existing files or symlinks and terminates a command that exceeds the declared stdout size. Commands have a finite execution timeout; version probes are capped at 30 seconds. It retains provenance and diagnostic logs. Candidate nodes run every time because the legacy executor's cache key does not yet include this entire runtime identity. The native package lock and executable checks are not immutable-container or full installed-library integrity proofs, and staging is not a security sandbox.

## Evidence and next work

`tests/fixtures/cwl-upstream/manifest.json` pins unmodified descriptors and their Apache-2.0 license to an upstream commit. `tests/test_universal_cwl_end_to_end.py` exercises real native execution, ordinary API discovery and queue execution, composition, byte-exact binary output, and refusal of wrong runtime/output expectations. It requires `BIONODULO_CWL_E2E_ENVIRONMENT` and the prefix mapping above; when explicitly enabled, missing tools fail instead of silently skipping.

These are development/conformance examples, not a preregistered held-out study. The next engineering work is descriptor acquisition at registry scale, broader standards/backends, automatic environment realization, streaming outputs, empirical semantic inference and evidence review. The PhD evaluation still needs independent expert contracts, held-out coverage and error rates, regeneration/maintenance measurements, and the proposed human study.
