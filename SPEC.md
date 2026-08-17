# BioNodulo v2 - Full Specification

## Overview
BioNodulo v2 is a visual bioinformatics workflow workbench with a node-based graph editor for constructing, executing, and sharing bioinformatics pipelines.

## Architecture
- **Backend**: Python 3.11+ / FastAPI / Uvicorn
- **Frontend**: React 19 / TypeScript / Vite / custom workflow canvas
- **Communication**: REST API + WebSocket for real-time execution updates
- **Execution**: Async queue-based with caching and environment isolation

## Project Structure
```
bionodulo-v2/
├── main.py                          # Entry point (uvicorn launcher)
├── server.py                        # FastAPI app factory
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Package metadata
├── bionodulo.yaml.example           # Config template
├── bionodulo/                       # Backend package
│   ├── __init__.py                  # Version info
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Settings dataclass, YAML loading
│   │   ├── paths.py                # Path utilities
│   │   └── events.py               # EventHub (pub/sub for WebSocket)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py               # All REST endpoints
│   │   ├── websocket.py            # WebSocket endpoint
│   │   └── schemas.py              # Pydantic request models
│   ├── nodes/
│   │   ├── __init__.py             # BaseNode, CommandNode, NodeRegistry exports
│   │   ├── base.py                 # BaseNode class
│   │   ├── command_node.py         # CommandNode (external tool wrapper)
│   │   ├── registry.py             # NodeRegistry (builtin + custom loading)
│   │   ├── schema_api.py           # Schema-based node definitions
│   │   ├── types.py                # Type compatibility checking
│   │   └── builtin/                # Built-in bioinformatics nodes
│   │       ├── __init__.py
│   │       ├── inputs.py           # FASTQ, FASTA, File, Directory, SampleSheet
│   │       ├── qc.py               # FastQC, MultiQC, QualiMap
│   │       ├── trimming.py         # fastp, Trimmomatic, Cutadapt
│   │       ├── alignment.py        # BWA mem/index, Bowtie2, Minimap2, STAR
│   │       ├── samtools.py         # sort, index, flagstat, view, merge
│   │       ├── variant.py          # bcftools, GATK HaplotypeCaller
│   │       ├── assembly.py         # SPAdes, MEGAHIT, Canu
│   │       ├── annotation.py       # Prokka, eggNOG, InterProScan
│   │       ├── phylogeny.py        # IQ-TREE, FastTree, RAxML
│   │       ├── rna_seq.py          # HISAT2, Salmon, Kallisto, featureCounts
│   │       ├── metagenomics.py     # Kraken2, Bracken, MetaPhlAn, HUMAnN
│   │       ├── utils.py            # Generic Command, View Text, Collect Files
│   │       └── hpc.py              # HPC job submission nodes
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── executor.py             # WorkflowExecutor with context
│   │   ├── queue.py                # RunQueue (async queue)
│   │   ├── cache.py                # CacheStore for result caching
│   │   ├── subprocess_runner.py    # Real subprocess execution
│   │   └── run_metadata.py         # RunRecord dataclass
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── schema.py               # Workflow Pydantic model
│   │   ├── graph.py                # Graph algorithms (topo sort, etc.)
│   │   ├── validation.py           # Workflow validation
│   │   ├── serialization.py        # Save/load workflows
│   │   └── export.py               # Export to SnakeMake, NextFlow
│   ├── converter/
│   │   ├── __init__.py
│   │   ├── snakemake_converter.py  # Import/export SnakeMake
│   │   ├── nextflow_converter.py   # Import/export NextFlow
│   │   ├── galaxy_converter.py     # Import/export Galaxy workflows
│   │   └── cwl_converter.py        # Import/export CWL
│   ├── hpc/
│   │   ├── __init__.py
│   │   ├── base.py                 # HPCBackend ABC
│   │   ├── slurm.py                # SLURM backend
│   │   ├── pbs.py                  # PBS/Torque backend
│   │   ├── sge.py                  # Sun Grid Engine backend
│   │   └── local.py                # Local execution fallback
│   ├── environments/
│   │   ├── __init__.py
│   │   ├── conda.py                # Conda/Mamba/Micromamba prefix generation
│   │   ├── containers.py           # Docker/Apptainer/Singularity
│   │   ├── model.py                # Environment spec dataclass
│   │   └── manager.py              # Environment CRUD, dependency tree, workflow env creation
│   ├── manager/
│   │   ├── __init__.py
│   │   ├── custom_nodes.py         # Custom node install/remove
│   │   ├── diagnostics.py          # Environment diagnostics
│   │   ├── runtime_installer.py    # Auto-install missing tools
│   │   ├── resolver.py             # Workflow dependency resolution engine
│   │   └── installer.py            # Async install jobs with progress tracking
│   ├── provenance/
│   │   ├── __init__.py
│   │   ├── workflow_embed.py       # Embed workflow in outputs
│   │   └── reports.py              # Execution reports
│   └── ai/
│       ├── __init__.py
│       └── assistant.py            # AI chat assistant
├── custom_nodes/                    # User custom nodes
│   └── example_node.py.example
├── docs/                            # Documentation
│   ├── architecture.md
│   ├── custom-nodes.md
│   ├── execution-model.md
│   ├── node-api.md
│   ├── workflow-format.md
│   └── help/                        # HTML help pages
│       ├── index.html
│       ├── getting-started.html
│       ├── nodes-reference.html
│       ├── templates-guide.html
│       ├── custom-nodes.html
│       ├── hpc-integration.html
│       └── workflow-converters.html
├── templates/                       # Workflow templates
│   ├── assembly_pipeline.json
│   ├── biopython_analysis_pipeline.json
│   ├── chip_seq_pipeline.json
│   ├── crispr_editing_pipeline.json
│   ├── deseq2_differential_expression.json
│   ├── differential_expression.json
│   ├── fastq_qc_pipeline.json
│   ├── long_read_ont_pipeline.json
│   ├── metabolomics_lcms_pipeline.json
│   ├── metagenomics_pipeline.json
│   ├── phylogenetics_pipeline.json
│   ├── pangenomics_graph_pipeline.json
│   ├── protein_structure_database_workflow.json
│   ├── proteomics_sage_percolator_pipeline.json
│   ├── r_visualization_pipeline.json
│   ├── rna_seq_pipeline.json
│   ├── robust_designer.json
│   ├── single_cell_pipeline.json
│   ├── spatial_transcriptomics_qc_clustering.json
│   ├── synthetic_biology_design_simulation.json
│   ├── variant_calling_pipeline.json
│   ├── wgbs_methylation_pipeline.json
│   ├── wgs_variant_pipeline.json
│   └── ...
├── web/                             # Frontend (React + Vite)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   └── src/
│       ├── main.tsx                 # Entry point
│       ├── App.tsx                  # Main app shell
│       ├── index.css                # Global styles / theme
│       ├── types.ts                 # TypeScript type definitions
│       ├── utils.ts                 # Shared utilities
│       ├── hooks/
│       │   ├── useWebSocket.ts
│       │   useWorkflow.ts
│       │   useObjectInfo.ts
│       │   useRuns.ts
│       │   useSettings.ts
│       │   useTheme.ts
│       │   └── useHistory.ts
│       ├── components/
│       │   ├── canvas/
│       │   │   ├── WorkflowCanvas.tsx
│       │   │   ├── MiniMap.tsx
│       │   │   └── CanvasControls.tsx
│       │   ├── nodes/
│       │   │   ├── NodePalette.tsx
│       │   │   ├── NodeEditor.tsx
│       │   │   └── NodeContextMenu.tsx
│       │   ├── layout/
│       │   │   ├── TopBar.tsx
│       │   │   ├── LeftRail.tsx
│       │   │   ├── RailPanel.tsx
│       │   │   ├── WorkflowTabs.tsx
│       │   │   └── BottomConsole.tsx
│       │   ├── panels/
│       │   │   ├── SettingsPanel.tsx       # Categorized settings
│       │   │   ├── HelpWikiPanel.tsx       # Full help/wiki system
│       │   │   ├── TemplatesPanel.tsx      # Rich template browser
│       │   │   ├── EnvironmentPanel.tsx    # Enhanced env manager
│       │   │   ├── NodeLibraryPanel.tsx    # Node browser/search
│       │   │   ├── WorkspacePanel.tsx      # File browser
│       │   │   ├── RunsPanel.tsx           # Run queue/history/logs
│       │   │   ├── ExportPanel.tsx         # Workflow export
│       │   │   ├── ImportPanel.tsx         # Workflow import/converters
│       │   │   └── HPCPanel.tsx            # HPC configuration
│       │   ├── modals/
│       │   │   ├── SettingsModal.tsx
│       │   │   ├── NodeEditorModal.tsx
│       │   │   ├── ExportModal.tsx
│       │   │   ├── ImportModal.tsx
│       │   │   ├── InstallConfirmModal.tsx
│       │   │   ├── AIWorkflowModal.tsx
│       │   │   └── GroupContextMenu.tsx
│       │   └── ui/
│       │       ├── Icon.tsx
│       │       ├── ColorPicker.tsx
│       │       ├── SearchBox.tsx
│       │       ├── StatusBadge.tsx
│       │       └── Tooltip.tsx
│       └── stores/
│           ├── workflowStore.ts
│           └── settingsStore.ts
├── envs/                            # Generated per-workflow environments (ignored)
├── examples/
│   ├── data/
│   │   └── README.md
│   └── workflows/
│       └── fastq_qc_pipeline.bionodulo.json
└── tests/                           # Test suite
    └── ...

## Key API Endpoints
- `GET /object_info` - List all node metadata
- `GET /object_info/{node_id}` - Single node metadata
- `POST /workflow/validate` - Validate workflow
- `POST /runs` - Submit workflow for execution
- `GET /queue` - Queue state
- `POST /queue/clear` - Clear pending queue
- `GET /history` - Execution history
- `GET /runs/{run_id}` - Run details
- `GET /config/effective` - Current settings
- `POST /ai/chat` - AI assistant
- `GET /workspace/files` - File tree
- `GET /manager/status` - Node manager status
- `GET /settings` - Get settings
- `POST /settings` - Save settings
- `GET /settings/{id}` - Get specific setting
- `POST /settings/{id}` - Set specific setting
- `GET /workflow_templates` - List available templates
- `GET /i18n` - Translations
- `POST /workflow/export` - Export workflow (snakemake, nextflow, etc.)
- `POST /workflow/import` - Import workflow (snakemake, nextflow, galaxy, cwl)
- `GET /hpc/status` - HPC connection status
- `POST /hpc/configure` - Configure HPC backend
- `POST /hpc/submit` - Submit job to HPC
- `GET /docs/{page}` - Serve help/wiki pages

## Settings System
Settings stored per-user in `bionodulo.settings.json`:
```json
{
  "bionodulo.theme": "system",
  "bionodulo.snapToGrid": false,
  "bionodulo.showMinimap": true,
  "bionodulo.linksHidden": false,
  "bionodulo.viewportLocked": false,
  "bionodulo.autoSave": "off",
  "bionodulo.queueHistorySize": 100,
  "bionodulo.fileExplorerDepth": 4,
  "bionodulo.showHiddenFiles": false,
  "bionodulo.strongHashing": false,
  "bionodulo.tooltipsEnabled": true,
  "bionodulo.confirmFileDelete": true,
  "bionodulo.preserveView": true,
  "bionodulo.llm.provider": "openai",
  "bionodulo.llm.model": "gpt-4.1-mini",
  "bionodulo.llm.baseUrl": "",
  "bionodulo.llm.apiKey": "",
  "bionodulo.llm.temperature": 0.2,
  "bionodulo.hpc.enabled": false,
  "bionodulo.hpc.backend": "slurm",
  "bionodulo.hpc.partition": "",
  "bionodulo.hpc.account": "",
  "bionodulo.hpc.modules": [],
  "bionodulo.hpc.container": ""
}
```

## Node Categories (Expanded)
1. **Input** - FASTQ, FASTA, File, Directory, SampleSheet, VCF, GFF
2. **Quality Control** - FastQC, MultiQC, QualiMap, Kraken2 (contamination)
3. **Read Preprocessing** - fastp, Trimmomatic, Cutadapt, BBTools
4. **Alignment** - BWA mem/index, Bowtie2, Minimap2, HISAT2, STAR
5. **SAM/BAM Processing** - samtools sort/index/view/flagstat/merge
6. **Variant Calling** - bcftools, GATK HaplotypeCaller, DeepVariant, FreeBayes
7. **Assembly** - SPAdes, MEGAHIT, Canu, Flye, Unicycler
8. **Annotation** - Prokka, Bakta, eggNOG-mapper, InterProScan
9. **Phylogenetics** - IQ-TREE, FastTree, RAxML, MAFFT, ClustalO
10. **RNA-Seq** - HISAT2, Salmon, Kallisto, featureCounts, DESeq2 (via R)
11. **Metagenomics** - Kraken2, Bracken, MetaPhlAn, HUMAnN, MaxBin
12. **ChIP-Seq** - MACS2, Homer, DeepTools
13. **Single Cell** - Cell Ranger, Seurat (via R)
14. **Spatial Transcriptomics** - Space Ranger, Squidpy, Scanpy, Seurat, Cell2location, Baysor
15. **Long Read** - Dorado, Chopper, NanoPlot, Modkit, Medaka
16. **Proteomics** - Sage, Percolator, FragPipe, MSFragger, MaxQuant, DIA-NN, OpenMS
17. **Protein Structure** - UniProt, AlphaFold DB, RCSB PDB
18. **Epigenomics** - Bismark, MethylDackel, DSS, Modkit, deepTools, Hi-C tooling
19. **CRISPR** - Guide RNA Design, Cas-OFFinder, CRISPResso2, MAGeCK
20. **Pangenomics** - PGGB, Minigraph, Minigraph-Cactus, vg, ODGI, Panacus, Panaroo
21. **Metabolomics** - XCMS, CAMERA, SIRIUS, MZmine, MetaboAnalystR, MS-DIAL
22. **Synthetic Biology** - SBOL, COPASI, iBioSim, Cello
23. **HPC** - SLURM submit, PBS submit, SGE submit
24. **Utility** - Generic Command, View Text, Collect Files, Merge VCF

## HPC Integration
- Toggle in settings panel
- Supports SLURM, PBS/Torque, SGE
- Auto-generates job scripts from workflows
- Monitors job status via scheduler APIs
- Converts local runs to HPC batch jobs

## Workflow Converters
- **Export**: SnakeMake, NextFlow, CWL, Galaxy, WDL
- **Import**: SnakeMake, NextFlow, CWL, Galaxy (parse and convert to node graph)

## Frontend Features
- Custom workflow node canvas
- Left rail with: Data, Nodes, Templates, Environments, Help, Console, Settings
- Settings modal with categorized settings
- Full help/wiki panel with searchable documentation
- Rich template browser with descriptions and previews
- HPC toggle in top bar
- Import/Export workflow modal with format selection
- AI workflow assistant chat
- Dark/light theme support
- Undo/redo history
- Group selection and manipulation
- Node search and palette
- Real-time execution status via WebSocket
