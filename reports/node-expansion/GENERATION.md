# Reproduce the 2026-09-29 generated node contracts

Run these commands from the repository root in a clean checkout of this branch.
The 387 additions comprise **373 generated contracts** and **14 separately authored
nodes**. The latter are source files in the repository and are not emitted by
these generators. Generation establishes command and metadata contracts; it does
not establish scientific or queue execution.

`generator-inputs.zip` contains 13 retained raw-capture directories under
`artifacts/`, plus a derived `registry.jsonl`. Its SHA-256 is
`62003df93e7981d89be4196174f6b3ed8e437535a6a1941c5c3071957d056a4c`
(542,768 bytes, 697 entries). ZIP entries are sorted, have fixed 1980-01-01
timestamps and fixed file permissions. The files within each capture directory
are byte-for-byte copies; no help page, ACD file, or probe result was rewritten.

The derived registry file contains the **166 exact original JSONL lines** whose
`biotoolsID` matches a generated EMBOSS program. The generator uses this file only
to decide whether each generated operation has its own bio.tools record or uses
the suite record. Its SHA-256 is
`6edf2bdae546e88fb6ec8a1e531943bc49f612ef8da0ee99c8529d0c9e24f4a2`
(683,086 bytes). It was filtered from the 107,072,317-byte snapshot at
`reports/biotools_registry/current/registry.jsonl`, SHA-256
`4bc2dff4e6f60b6098876977a3ea5228745d6891c316a7fe3fd3d830edadac13`.
Each selected line retained its original bytes and newline. The other six
generators do not read the registry snapshot; the subcommand generator's
`--snapshot` option is retained only for old call-site compatibility.

Extract the inputs locally:

```powershell
python -c "import zipfile; zipfile.ZipFile('reports/node-expansion/generator-inputs.zip').extractall('reports/node-expansion/generator-inputs')"
$generatorBundle = 'reports/node-expansion/generator-inputs'
```

The source help pages came from the following container builds. The archive hash
pins the captured inputs even where an immutable image digest was not recorded.
The ACDs are EMBOSS's own formal parameter definitions. The `*-required`
directories contain empirical required-flag probes, and `vcflib-argprobe`
contains cached value-versus-switch probes; the latter keeps regeneration from
requiring Docker.

| Family | Captured source |
| --- | --- |
| csvtk | `quay.io/biocontainers/csvtk:0.31.0--h9ee0642_0` |
| EMBOSS | `quay.io/biocontainers/emboss:6.6.0--h0f19ade_14`; receipt image digest `sha256:a9bf499a690de7950a3f553793ea45daa947c63946a43edaefdbcfb0e9960a97` |
| SeqFu | `quay.io/biocontainers/seqfu:1.28.0--h41da26b_0` |
| SeqKit | `quay.io/biocontainers/seqkit:2.13.0--he881be0_0` |
| TaxonKit | `quay.io/biocontainers/taxonkit:0.20.0--h9ee0642_1`; digest `sha256:c27f1ecebde5e98ba09693dd3046814464a9d3ad2c944fba5a0be560ee643c7d` |
| UniKmer | `quay.io/biocontainers/unikmer:0.20.0--h9ee0642_0`; digest `sha256:92654c4223ba021d9d11493de3d1aae84cef2710037a8d052cd33ed4cea29136` |
| vcflib | `quay.io/biocontainers/vcflib:1.0.15--h3fa9d83_1`; digest `sha256:838ddab39b0af484f51c1b08f032f47e4ca9e402a8d36d1d4c6f7c46e031d034` |

Re-run the seven family generators. The target family directories must contain
the repository's hand-written modules, because the generators detect operations
they already cover. Run this in a disposable checkout if comparing output with
the reviewed generated files.

```powershell
python scripts/generate_subcommand_nodes.py --help-dir "$generatorBundle/artifacts/csvtk-help" --binary csvtk --family bionodulo/nodes/builtin/csvtk_family --manifest reports/node-expansion/csvtk-generated.json --commit v0.31.0 --required-dir "$generatorBundle/artifacts/csvtk-required" --skip-subcommands version
python scripts/generate_emboss_nodes.py --acd-dir "$generatorBundle/artifacts/emboss-acd" --nodes-dir bionodulo/nodes/builtin/emboss_family --manifest reports/node-expansion/emboss-generated.json --snapshot "$generatorBundle/registry.jsonl"
python scripts/generate_subcommand_nodes.py --help-dir "$generatorBundle/artifacts/seqfu-help" --binary seqfu --family bionodulo/nodes/builtin/seqfu_family --manifest reports/node-expansion/seqfu-generated.json --commit 'seqfu 1.28.0' --required-dir "$generatorBundle/artifacts/seqfu-required" --base-class SeqfuBase --input-port input --input-description 'Input sequence file' --output-mode auto --documentation-url https://telatin.github.io/seqfu2/ --tabular false --skip-subcommands deinterleave,interleave,less,msa,view
python scripts/generate_subcommand_nodes.py --help-dir "$generatorBundle/artifacts/seqkit-help" --binary seqkit --family bionodulo/nodes/builtin/seqkit_family --manifest reports/node-expansion/seqkit-generated.json --commit v2.13.0 --required-dir "$generatorBundle/artifacts/seqkit-required" --base-class SeqkitBase --input-port sequence --input-description 'Input FASTA/FASTQ file' --output-mode flag --output-flag=-o --documentation-url https://bioinf.shenwei.me/seqkit/ --tabular false --skip-subcommands version
python scripts/generate_subcommand_nodes.py --help-dir "$generatorBundle/artifacts/taxonkit-help" --binary taxonkit --family bionodulo/nodes/builtin/taxonkit_family --manifest reports/node-expansion/taxonkit-generated.json --commit v0.20.0 --base-class TaxonkitBase --input-port input --input-description 'Input file: TaxId list, taxdump files, or profile, depending on the subcommand' --output-mode flag --output-flag=--out-file --documentation-url https://bioinf.shenwei.me/taxonkit/ --tabular false --promote-global data-dir --skip-subcommands version
python scripts/generate_subcommand_nodes.py --help-dir "$generatorBundle/artifacts/unikmer-help" --binary unikmer --family bionodulo/nodes/builtin/unikmer_family --manifest reports/node-expansion/unikmer-generated.json --commit 0.20.0 --required-dir "$generatorBundle/artifacts/unikmer-required" --base-class UnikmerBase --input-port input --input-description 'Input k-mer file (.unik) or FASTA/Q file' --output-mode auto --documentation-url https://bioinf.shenwei.me/unikmer/ --tabular false --skip-subcommands version
python scripts/generate_vcflib_nodes.py --help-dir "$generatorBundle/artifacts/vcflib-help" --family bionodulo/nodes/builtin/vcflib_family --manifest reports/node-expansion/vcflib-generated.json --arg-probe-dir "$generatorBundle/artifacts/vcflib-argprobe" --skip vcfplotaltdiscrepancy.sh,vcfplottstv.sh,vcfprintaltdiscrepancy.sh
python scripts/check_generated_manifests.py reports/node-expansion
```

The EMBOSS parser discovers ten additional split-bracket ACD programs that are
explicitly marked `skipped_pending_contract_review`. The vcflib generator also
excludes the unsupported `bgziptabix` shell wrapper. These exclusions keep the
reviewed generated set at 373. csvtk's `version` command is also excluded: its
help declares no data input, and the pinned CLI prints to stdout without writing
the generated node's promised output file.

An isolated extraction-and-regeneration check matched **all seven manifests and
all 373 generated Python modules byte for byte**: csvtk (43), SeqFu (20), SeqKit
(31), TaxonKit (8), UniKmer (23), EMBOSS (166), and vcflib (82). The csvtk refresh
applies the shared renderer's token lookup to its 43 nodes; no csvtk node declares
a custom token map, so the rendered flags remain the same. Its manifest now records
global-flag accounting in the current schema. UniKmer's earlier duplicate name in
the `unikmer_grep` docstring was normalized by the same family invocation above.
Focused csvtk and generated-contract tests passed, along with the 373-node
manifest check and Ruff. This regeneration check does not replace external
execution or scientific oracles for all 373 operations.
