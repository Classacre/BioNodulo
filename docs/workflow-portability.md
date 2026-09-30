# Workflow portability

BioNodulo exports a deliberately limited executable subset. An export fails when a node, port, edge, or widget cannot be represented by that subset. The JSON workflow format remains the lossless native save format.

| Format | Exported form | Current executable scope | Import |
| --- | --- | --- | --- |
| Snakemake | `.smk` / Snakefile | FastQC `reads → report_dir` and MultiQC `reports → report, data_dir`, using one root read file and their scalar options; FastQC adapter, contaminant, and limits files are rejected until staged correctly | Unchanged BioNodulo export restores the original graph. A simple foreign shell-rule file imports only as a structural draft. |
| Nextflow | `.nf` / DSL2 script | The same FastQC and MultiQC graph and scalar options, with one incoming edge per node; file-valued FastQC options are likewise rejected | Unchanged BioNodulo export restores the original graph. A simple foreign DSL2 file imports only as a structural draft. |
| CWL | `.cwl-bundle.json` containing `workflow.cwl`, `tools/*.cwl`, and a manifest | `extract_columns`, `filter_rows`, `merge_tables`, `normalize_data`, and `replace_text` through the BioNodulo Python runner | Unchanged bundle restores the original graph. Foreign JSON CWL is a structural draft only; YAML CWL is currently rejected. |
| Galaxy | `.ga` JSON | Graph interchange only; local Galaxy tool IDs, versions, and installed wrappers have not been validated | Unchanged BioNodulo export restores the original graph. Foreign `.ga` is a structural draft only. |

WDL is not supported. Other BioNodulo nodes, arbitrary shell commands, complex foreign directives, scatter/conditionals, and unsupported multi-source wiring are rejected rather than guessed. External structural drafts contain `generic_command` nodes and return an API warning; review and map every tool and input before running them in BioNodulo.

Snakemake and Nextflow exports require the real tools on the execution host or a configured container/Conda environment. Each root input key uses the sanitized node ID followed by `_input`; inspect the generated file for its exact key. The example below uses a FastQC node whose ID is `qc`. The output directory is created by the generated workflow:

```sh
snakemake --snakefile Snakefile --cores 1 --config qc_input=sample.fastq
nextflow run main.nf --qc_input sample.fastq
```

The CWL response is a JSON file map, not one standalone `.cwl` file. Unpack the keys into one directory before running `cwltool --no-container workflow.cwl job.json`. The five built-in tools call `python -m bionodulo.converter.cwl_node_runner`, so the target Python environment must have BioNodulo installed. File input ports must be supplied by the CWL job or an edge; a nonempty inline file parameter is rejected rather than discarded. The JSON bundle can be pasted directly into BioNodulo's CWL import API. Individual external `workflow.cwl` files need their referenced `tools/*.cwl` files next to them; missing tools return a client error.

Native QC exports preserve MultiQC's boolean `force` option and isolate its generated report/data filenames in a temporary directory. Nextflow stages input basenames under a separate directory so input names cannot collide with the declared outputs. Both tools still require the root input binding described above. Real Nextflow collision fixtures named `multiqc_report_data`, `data_dir_output`, and `report_dir_output` produced the expected outputs while preserving source checksums.

Connected CWL inputs in this subset are file ports. Promoting scalar widgets into connected ports is rejected until their native scalar bindings can be represented correctly.

An integrity marker in each BioNodulo export restores its original node IDs, port names, widgets, parameters, positions, notes, annotations, and edges when reimported unchanged. Editing the native source or bundle invalidates that marker and import fails rather than silently restoring stale graph metadata. This marker is an integrity check for round trips, not a security signature or a claim that arbitrary foreign workflow syntax is equivalent.

The standalone WES request builder uses explicit `input_bindings` keyed by the exported document's root inputs: for example, `extract_table` for a CWL node named `extract`, or `qc_input` for a native QC node named `qc`. It refuses missing or unknown bindings, local file paths, overrides of embedded input paths, and Galaxy structural exports. It does not upload input files or contact a WES service. The chosen endpoint must access or stage each supplied URI, map scheduler inputs into engine-accessible files, and advertise the submitted language/version; callers can set `workflow_type_version` accordingly. The generated CWL attachments and parameters passed a local cwltool execution with an isolated synthetic HTTP input and independently checked output rows. This does not verify an external WES service. The [GA4GH WES contract](https://ga4gh.github.io/workflow-execution-service-schemas/docs/) defines these service responsibilities and language-specific parameter conventions.

The 2026-09-30 local portability audit executed a one-read FASTQ through generated workflows with real FastQC 0.12.1 and MultiQC 1.31 under Snakemake 9.26.1 and Nextflow 25.10.7. These workflows were generated from the editor's actual `position`, `params`, and `node_info` payload using packaged node metadata. Both FastQC reports recorded one sequence, and both MultiQC reports contained the exact configured literal title and parsed FastQC data. `cwltool` 3.3 executed each of the five built-in transforms from the same editor payload shape. The checked outputs matched the expected extracted columns, filtered rows, left join, text replacements, and min-max normalization values across both axes. This is a small deterministic fixture, not scale validation or proof for other tools.

See the [Snakemake documentation](https://snakemake.readthedocs.io/), [Nextflow process reference](https://www.nextflow.io/docs/latest/process.html), and [CWL v1.2 specification](https://www.commonwl.org/v1.2/) for the native formats.
