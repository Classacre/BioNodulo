# Third-Party Notices

BioNodulo is paid software distributed under the BioNodulo Closed Alpha
Commercial License. Third-party components are not relicensed by BioNodulo and
remain subject to their own license terms.

This notice is an engineering summary for the current closed-alpha repository.
Before a public, institutional, hosted, or on-premises release, generate a full
software bill of materials and review the exact shipped artifacts with counsel.

## Application Dependencies

The core Python and web application currently depends primarily on permissive
open-source packages, including MIT, BSD-style, Apache-2.0, ISC, and similar
licenses.

Examples include:

- Backend libraries such as FastAPI, Pydantic, Uvicorn, SQLAlchemy, Alembic,
  PyYAML, httpx, Redis clients, LangChain, LangGraph, LiteLLM, and related
  packages.
- Frontend libraries such as React, React DOM, Jotai, i18next, Yjs,
  y-websocket, y-protocols, react-use-websocket, and Fuse.js.
- Development and build tools such as TypeScript, Vite, Vitest, ESLint,
  Playwright, Ruff, Mypy, and Pytest.

Permissive dependencies generally allow commercial use, but their copyright,
license, and attribution notices must be preserved where required.

## External Bioinformatics Tools

BioNodulo nodes may detect, invoke, or help install external command-line tools
and runtime environments through Conda, Bioconda, Pixi, Docker, Apptainer,
system PATH, or user configuration.

Those tools are independent third-party software. Their licenses may include
GPL, LGPL, Artistic, Apache-2.0, BSD, MIT, proprietary vendor terms, academic
terms, citation requirements, or dataset-specific terms. BioNodulo does not
grant rights to those tools.

Examples of external tools that require separate license attention include:

- GPL or copyleft-licensed tools commonly used in bioinformatics workflows,
  such as FastQC, MultiQC, BWA, Bowtie2, STAR, SPAdes, Trimmomatic, R, and
  related packages.
- Proprietary or vendor-controlled tools such as Cell Ranger, which should be
  supplied and licensed by the user or institution rather than redistributed by
  BioNodulo.
- R/Bioconductor packages and Conda/Bioconda packages, which may have their own
  license, citation, redistribution, and source-availability obligations.

## Distribution Guidance

BioNodulo installers, containers, managed environments, and hosted deployments
must not imply that third-party tools are licensed under the BioNodulo license.

For commercial release readiness:

- Generate and review an SBOM for Python, npm, Conda/Pixi, OS, Docker, and
  model/API dependencies.
- Preserve required third-party notices in distributed artifacts.
- Avoid bundling proprietary vendor tools unless BioNodulo has explicit
  redistribution rights.
- Treat GPL/LGPL tools carefully when distributing binaries, containers, or
  managed environments.
- Require users or institutions to bring their own licenses for restricted
  tools and services.
