---
name: bionodulo-workflows
description: Inspect, prepare, validate, and run BioNodulo bioinformatics workflows using the connected BioNodulo MCP tools.
---

# BioNodulo workflows

Use the `bionodulo` MCP server when the user asks about their BioNodulo account, workflows, uploaded files, node catalog, credits, or runs. The remote server connects to the user's BioNodulo account through the host's OAuth sign-in. If authentication is required, let the host complete its normal sign-in flow.

For a new workflow, find suitable nodes with `search_node_types`, inspect their requirements with `get_node_info`, and assemble a workflow matching those schemas. Use `validate_workflow` before saving or submitting it. For an existing workflow, use `list_workflows` and `get_workflow`; use `update_workflow` only after identifying the intended workflow and changes.

When the user supplies Nextflow, Snakemake, CWL, or Galaxy text, use `import_workflow` to draft a BioNodulo graph, review its portability warnings, and validate the result before saving. Use `export_workflow` for a requested portable representation; explain any reported gaps instead of claiming the exported workflow runs elsewhere without verification.

Before a cloud run, inspect input files with `list_files`, check available credits with `get_credit_balance`, and estimate cost with `estimate_run_cost` when resource requirements are known. Submit only when the user requested execution and the workflow, inputs, and expected cost are clear. Use `submit_run`, then `get_run_status`, `get_run_events`, and `get_run_outputs` to report the actual result. Do not imply a queued run is complete.

For an upload, `get_upload_url` only prepares a temporary destination. The authorized file's bytes must be transferred with the declared content type and size, then `complete_upload` must verify it before the file can be used as workflow input. Never report an upload as complete from the URL alone.

For account or run questions, use the smallest relevant read tools, such as `get_account_info`, `list_runs`, or `get_run_status`. Use `cancel_run` only when the user asks to stop a specific run. Never request or store Clerk backend keys, session JWTs, or service credentials in the plugin.
