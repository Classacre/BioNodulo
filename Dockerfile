# BioNodulo v2 - Container image for cloud GPU deployment (RunPod, etc.)
FROM python:3.11-slim-bookworm

# Install system dependencies for bioinformatics tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    ca-certificates \
    build-essential \
    r-base \
    r-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Install common R packages for plotting and bioinformatics
RUN R -e "install.packages(c('ggplot2','dplyr','tidyr','readr','reshape2','patchwork','pheatmap','RColorBrewer','ape','vegan'), repos='https://cloud.r-project.org/')"

# Install Bioconductor packages
RUN R -e "if (!requireNamespace('BiocManager', quietly=TRUE)) install.packages('BiocManager', repos='https://cloud.r-project.org/'); BiocManager::install(c('DESeq2','edgeR','limma','Biostrings','GenomicRanges','rtracklayer','SummarizedExperiment','tximport','ComplexHeatmap'), ask=FALSE)"

# Install BioPython
RUN pip install --no-cache-dir biopython

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build frontend
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && cd web && npm install && npm run build \
    && apt-get purge -y nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Expose port
EXPOSE 8000

# Run with 0.0.0.0 to accept remote connections
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
