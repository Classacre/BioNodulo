# Reports

These are retained measurements and reproducible examples, not a declaration
that every registry entry can execute. Read each report's date, input snapshot
and validation boundary before quoting a result.

| Location | Contents |
| --- | --- |
| Registry toolbox | [Snapshot manifest](registry-toolbox/snapshot-manifest.json), [definition coverage](registry-toolbox/coverage.json), [API coverage](registry-toolbox/api-coverage.json) and [typed-CWL acquisition](registry-toolbox/typed-cwl-acquisition.json); see the [toolbox guide](../docs/GENERATED_REGISTRY_TOOLBOX.md) |
| [biotools_registry](biotools_registry/README.md) | Historical annotation/contract reports and current synchronization instructions |
| [oci-reference](oci-reference/README.md) | Experimental container-profile resolution, execution, cancellation and timeout evidence |
| [contract_demo](contract_demo/) | Deterministic contract-chain fixture and example RO-Crate; reproduced by `scripts/run_contract_demo.py` |
| [roundtrip_fidelity](roundtrip_fidelity/fidelity.md) | Workflow-format round-trip measurements; reproduced by `scripts/roundtrip_fidelity.py` |
| [adaptability-note.md](adaptability-note.md) | Scope and limitations of the RNA-seq structural compatibility tests |

Keep raw registry downloads in ignored snapshot directories. Put ad-hoc logs,
screenshots and local QA output under ignored `artifacts/` instead of adding
another report tree. Retain a report when it supports a reproducible test,
release decision or measured scientific claim.
