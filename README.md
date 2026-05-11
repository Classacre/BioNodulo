# BioNodulo v2

**Visual bioinformatics pipelines, node by node.**

BioNodulo is a professional-grade visual workflow workbench for bioinformatics. Build, execute, and share complex bioinformatics pipelines using an intuitive node-based graph editor.

## Features

- **Visual Node Editor** - Drag-and-drop canvas for building workflows with 100+ built-in bioinformatics nodes
- **100+ Bioinformatics Nodes** - Covering QC, alignment, variant calling, assembly, RNA-Seq, metagenomics, phylogenetics, ChIP-Seq, single cell analysis, and more
- **10 Pre-built Templates** - FASTQ QC, RNA-Seq, Variant Calling, Metagenomics, Assembly, Phylogenetics, ChIP-Seq, Differential Expression, WGS Variant, Single Cell
- **HPC Integration** - Submit workflows to SLURM, PBS/Torque, or SGE clusters with a single toggle
- **Workflow Converters** - Import and export workflows between SnakeMake, NextFlow, CWL, Galaxy, and BioNodulo JSON formats
- **Settings System** - ComfyUI-inspired per-user settings with categories (Appearance, Canvas, Execution, LLM, HPC, Files)
- **Help / Wiki System** - Built-in searchable documentation covering all features
- **AI Assistant** - Chat-based workflow builder assistant
- **Environment Manager** - Conda, Mamba, Micromamba, Docker, and Apptainer support
- **Custom Nodes** - Extensible plugin system for adding new tools
- **Dark/Light Theme** - Full theme support with system detection
- **Multi-tab Workflows** - Work on multiple workflows simultaneously
- **Undo/Redo** - Full history support

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for frontend development only - pre-built frontend included)

### Installation

```bash
# Clone or extract the project
cd bionodulo-v2

# Install Python dependencies
pip install -r requirements.txt

# The frontend is pre-built in web/dist/
# To rebuild it (optional):
cd web && npm install && npm run build
```

### Running

```bash
# Start the server
python main.py

# Or with options
python main.py --host 0.0.0.0 --port 8000 --project-root ./workspace

# Development mode with auto-reload
python main.py --dev

# Safe mode (mock tool execution)
python main.py --mock-tools

# With custom config
python main.py --config bionodulo.yaml
```

Then open http://localhost:8000 in your browser.

### Using HPC Mode

1. Click the **HPC** toggle in the top bar
2. Open the HPC panel (Ctrl+5) and configure your scheduler
3. Set partition, account, resources, and modules
4. Click **Test Connection** to verify
5. Run your workflow - it will be submitted as a batch job

### Importing Workflows

Click the **Import** button in the top bar and paste workflow code from:
- SnakeMake (.smk)
- NextFlow (.nf)
- CWL (.cwl)
- Galaxy (.ga)
- BioNodulo JSON (.json)

### Creating Custom Nodes

1. Copy `custom_nodes/example_node.py.example` to `custom_nodes/my_node.py`
2. Edit the node class with your tool's parameters
3. Restart BioNodulo - your node appears in the palette automatically

## Project Structure

```
bionodulo-v2/
├── main.py                    # Entry point
├── server.py                  # FastAPI app
├── pyproject.toml             # Package metadata
├── requirements.txt           # Python dependencies
├── bionodulo.yaml.example     # Configuration template
├── bionodulo/                 # Backend package
│   ├── core/                  # Config, events, paths
│   ├── api/                   # REST API routes, WebSocket
│   ├── nodes/                 # Node system
│   │   ├── builtin/           # 100+ bioinformatics nodes
│   │   ├── base.py            # BaseNode class
│   │   ├── command_node.py    # External tool wrapper
│   │   └── registry.py        # Node discovery & loading
│   ├── execution/             # Execution engine
│   ├── workflow/              # Workflow validation, serialization
│   ├── converter/             # SnakeMake, NextFlow, CWL, Galaxy
│   ├── hpc/                   # SLURM, PBS, SGE backends
│   ├── environments/          # Conda, Docker, Apptainer
│   ├── manager/               # Custom nodes, diagnostics
│   ├── provenance/            # Workflow embedding, reports
│   └── ai/                    # AI assistant
├── custom_nodes/              # Your custom nodes
├── templates/                 # 10 pre-built workflow templates
├── docs/help/                 # HTML documentation
├── envs/                      # Environment YAML specs
├── examples/workflows/        # Example workflows
├── web/                       # Frontend (React + Vite)
│   ├── dist/                  # Pre-built frontend
│   └── src/                   # Source code
└── tests/                     # Test suite
```

## Node Categories

| Category | Tools | Description |
|----------|-------|-------------|
| Input | FASTQ, FASTA, VCF, GFF, File, Directory | Data loading nodes |
| Quality Control | FastQC, MultiQC, QualiMap | Sequence quality assessment |
| Read Preprocessing | fastp, Trimmomatic, Cutadapt | Adapter trimming and filtering |
| Alignment | BWA, Bowtie2, Minimap2, STAR, HISAT2 | Read alignment |
| SAM/BAM Processing | samtools sort, index, flagstat, view, merge | Alignment processing |
| Variant Calling | GATK, bcftools, FreeBayes | SNP/indel detection |
| Assembly | SPAdes, MEGAHIT, Flye, Canu | Genome assembly |
| Annotation | Prokka, Bakta, eggNOG | Genome annotation |
| Phylogenetics | MAFFT, IQ-TREE, FastTree, RAxML | Tree construction |
| RNA-Seq | Salmon, Kallisto, featureCounts, StringTie | Expression analysis |
| Metagenomics | Kraken2, Bracken, MetaPhlAn, HUMAnN | Microbial profiling |
| ChIP-Seq | MACS2, BEDTools, deepTools | Peak calling |
| Single Cell | Cell Ranger | scRNA-seq analysis |
| HPC | SLURM, PBS, SGE submit | Cluster job submission |
| Utility | Generic Command, View Text, Collect Files | Helper nodes |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+F | Open node palette |
| Ctrl+R | Run workflow |
| Ctrl+S | Save workflow |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+A | Select all nodes |
| Ctrl+G | Group selected nodes |
| Delete | Delete selected nodes |
| Ctrl+1-7 | Toggle left rail panels |
| Ctrl+, | Open Settings |
| Alt+Drag | Pan canvas |
| Double-click node | Edit node parameters |
| Right-click canvas | Node palette |

## Configuration

Copy `bionodulo.yaml.example` to `bionodulo.yaml` and customize:

```yaml
project_root: ./workspace
tool_paths:
  bwa: /usr/bin/bwa
  samtools: /usr/bin/samtools
  gatk: /opt/gatk/gatk
hpc:
  enabled: false
  backend: slurm
  partition: normal
  cpus_per_task: 4
llm:
  provider: openai
  model: gpt-4.1-mini
  api_key: your-key-here
```

## License

BioNodulo is an independent bioinformatics workflow platform inspired by the excellent work of the ComfyUI team. It is not a fork of ComfyUI but shares architectural patterns and design philosophy.
