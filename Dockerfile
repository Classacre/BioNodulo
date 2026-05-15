# syntax=docker/dockerfile:1
# BioNodulo v2 — Container image for cloud GPU deployment (RunPod, etc.)
FROM python:3.11-slim-bookworm

# 1. System dependencies (rarely changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl ca-certificates build-essential \
    r-base r-base-dev \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# 2. R packages (changes occasionally) — cache downloaded packages
RUN --mount=type=cache,target=/tmp/Rtmp \
    R -e "install.packages(c('ggplot2','dplyr','tidyr','readr','reshape2','patchwork','pheatmap','RColorBrewer','ape','vegan'), repos='https://cloud.r-project.org/')"

RUN --mount=type=cache,target=/tmp/Rtmp \
    R -e "if (!requireNamespace('BiocManager', quietly=TRUE)) install.packages('BiocManager', repos='https://cloud.r-project.org/'); BiocManager::install(c('DESeq2','edgeR','limma','Biostrings','GenomicRanges','rtracklayer','SummarizedExperiment','tximport','ComplexHeatmap'), ask=FALSE)"

# 3. Python dependencies (changes occasionally)
WORKDIR /app
COPY requirements.lock .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.lock

# 4. Frontend build (changes moderately)
COPY web/package*.json ./web/
RUN --mount=type=cache,target=/root/.npm \
    cd web && npm install
COPY web/ ./web/
RUN cd web && npm run build

# 5. Application code (changes frequently) — LAST
COPY . .

EXPOSE 8000
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
