<p align="center">
  <img src=".github/assets/logo.svg" alt="BioNodulo logo" width="120" />
</p>

<h1 align="center">BioNodulo</h1>

<p align="center">
  <strong>Visual bioinformatics pipelines, node by node.</strong>
</p>

<p align="center">
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2FClassacre%2FBioNodulo%2Fmain%2Fpyproject.toml&amp;query=%24.project.version&amp;label=version&amp;color=0d9488&amp;logo=github" alt="Version" /></a>
  <a href="https://discord.gg/baNKVhZq6k"><img src="https://img.shields.io/badge/Discord-Join%20BioNodulo-5865F2?logo=discord&amp;logoColor=white" alt="Discord" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="License" /></a>
  <a href="https://colab.research.google.com/github/Classacre/BioNodulo/blob/main/notebooks/BioNodulo_Colab.ipynb"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab" /></a>
  <a href="mcp/"><img src="https://img.shields.io/badge/MCP-Server-6B5B95?logo=modelcontextprotocol&amp;logoColor=white" alt="MCP Server" /></a>
  <a href="mcp/"><img src="https://img.shields.io/badge/Claude-D97757?logo=claude&amp;logoColor=fff" alt="Claude" /></a>
  <a href="mcp/"><img src="https://img.shields.io/badge/Codex-412991?logo=openai&amp;logoColor=white" alt="Codex" /></a>
</p>

Build, run and share bioinformatics workflows in a visual node editor. Use the desktop app, run from source, or use the hosted platform.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/screenshots/dark/app.png" />
    <source media="(prefers-color-scheme: light)" srcset=".github/assets/screenshots/light/app.png" />
    <img src=".github/assets/screenshots/light/app.png" alt="BioNodulo visual node editor" width="900" />
  </picture>
</p>

## Get started

- **Desktop and cloud:** [bionodulo.com](https://bionodulo.com)
- **User documentation:** [docs.bionodulo.com](https://docs.bionodulo.com)
- **Notebook trial:** [Open in Colab](https://colab.research.google.com/github/Classacre/BioNodulo/blob/main/notebooks/BioNodulo_Colab.ipynb)

BioNodulo supports local and HPC execution, isolated tool environments,
workflow import/export, collaborative editing and an AI assistant. The catalog
includes executable bioinformatics nodes and explicitly labeled reference-only
bio.tools entries. See the [template catalog](docs/templates.md) and
[tool integration profiles](docs/tool-integration.md) for coverage and limits.

### Run from source

Use Python 3.11+ and Node.js 24 (see [`.nvmrc`](.nvmrc)). In an activated
Python virtual environment:

```sh
python -m pip install -e .
cd web
npm ci
npm run build
cd ..
python main.py
```

Open `http://localhost:8000`. Bioinformatics commands need their declared tool
environments; some workflows also need reference datasets or external services.
See [development setup](docs/development.md) for live reload, tests and checks,
and [Windows execution](docs/desktop/windows-local-execution.md) for WSL setup.

## Repository map

| Path | Contents |
| --- | --- |
| `bionodulo/` | Python API, node catalog, workflow engine and integrations |
| `web/` | React/TypeScript editor built with Vite |
| `desktop/` | Tauri desktop app and packaging |
| `mcp/` | MCP server and client installation instructions |
| `templates/` | Bundled workflows, thumbnails and small smoke-test inputs |
| `examples/`, `notebooks/` | Example workflows and Colab launcher |
| `tests/` | Backend tests and fixtures; frontend tests live in `web/` |
| `scripts/` | Catalog generation, validation and maintenance commands |
| `docs/` | Architecture, development and feature guides |
| `reports/` | Dated measurements and reproducible evidence |
| `data/` | Committed research/example datasets |
| `alembic/` | Database migration configuration |

`main.py` starts the application and `server.py` assembles the FastAPI services.
Local runs, workspaces, environments and build output are ignored by Git.
The hosted website, documentation site and cloud infrastructure are maintained
in the separate `bionodulo-website` repository.

## Developer guides

- [Documentation index](docs/README.md)
- [Tool Atlas](docs/tool-atlas.md) and [builtin expansion handbook](docs/builtin-expansion-playbook.md)
- [Architecture](docs/architecture.md)
- [Development and checks](docs/development.md)
- [Maintenance scripts](scripts/README.md)
- [Desktop app](desktop/README.md)
- [MCP server](mcp/README.md)
- [Custom nodes](docs/help/custom-nodes.md)

## License

[GNU General Public License v3](LICENSE). Third-party tools, datasets,
containers, models and services retain their own license terms; see
[Third-Party Notices](THIRD_PARTY_NOTICES.md).
