// Runtime inputs for the packaged backend. New bundled data files must be
// named here so local files in data/ do not silently enter an installer.
import { cp, lstat, mkdir, realpath, rm } from "node:fs/promises";
import path from "node:path";

export const BACKEND_DIRECTORY_ENTRIES = new Set([
  "bionodulo",
  "web/dist",
  "templates",
  "docs/help",
  "examples/workflows",
]);

const BUNDLED_DATA_FILES = [
  "constructs.tsv",
  "egfp_u55762.fasta",
  "glori/GSM6432590_293T-mRNA-1_35bp_m2.totalm6A.FDR.csv.gz",
  "glori/GSM6432591_293T-mRNA-2_35bp_m2.totalm6A.FDR.csv.gz",
  "glori/GSM6432592_293T-UN_expression.csv.gz",
  "hsapiens_codon_usage.tsv",
  "il12b_nm002187.fasta",
  "insulin_nm000207.fasta",
  "luc_m15077.fasta",
  "openvaccine/RYOS1_50C_0000.rdat",
  "openvaccine/RYOS1_MG50_0000.rdat",
  "openvaccine/RYOS1_MGPH_0000.rdat",
  "openvaccine/RYOS_FULL_23Jul2021.json",
  "rbd_nc045512_22517_23185.fasta",
  "samples.csv",
  "wt1_nm000378.fasta",
];

export const BACKEND_ENTRIES = [
  "main.py",
  "server.py",
  "pyproject.toml",
  "README.md",
  "LICENSE",
  "THIRD_PARTY_NOTICES.md",
  "bionodulo.yaml.example",
  ...BACKEND_DIRECTORY_ENTRIES,
  ...BUNDLED_DATA_FILES.map(name => `data/${name}`),
  "custom_nodes/example_node.py.example",
];

const LOCAL_DIRECTORIES = new Set([
  ".git", ".venv", "venv", ".pixi", "__pycache__", ".pytest_cache",
  ".mypy_cache", ".ruff_cache", "node_modules",
]);

export function isBackendFile(relativePath) {
  const parts = relativePath.split(/[\\/]/);
  return !parts.some(part =>
    LOCAL_DIRECTORIES.has(part) || part === ".env" || part.startsWith(".env.") ||
    /\.(?:py[co]|log|tmp|bak)$/.test(part)
  );
}

function isWithin(parent, candidate) {
  const relative = path.relative(parent, candidate);
  return relative === "" || (relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative));
}

/** Validate the source and destination before replacing a previous staging tree. */
export async function stageBackend(source, destination, assetsRoot) {
  const sourcePath = path.resolve(source);
  const destinationPath = path.resolve(destination);
  const assetsPath = path.resolve(assetsRoot);
  if (path.dirname(destinationPath) !== assetsPath || path.basename(destinationPath) !== "bionodulo-backend") {
    throw new Error("Backend staging destination must be desktop/assets/bionodulo-backend");
  }

  const assetsInfo = await lstat(assetsPath);
  if (!assetsInfo.isDirectory() || assetsInfo.isSymbolicLink()) {
    throw new Error("Backend assets directory must be a real directory");
  }
  const sourceInfo = await lstat(sourcePath);
  if (!sourceInfo.isDirectory() && !sourceInfo.isSymbolicLink()) {
    throw new Error("Backend source must be a directory");
  }
  const destinationInfo = await lstat(destinationPath).catch(error => {
    if (error.code === "ENOENT") return null;
    throw error;
  });
  if (destinationInfo && (!destinationInfo.isDirectory() || destinationInfo.isSymbolicLink())) {
    throw new Error("Backend staging destination must be a real directory");
  }

  const sourceReal = await realpath(sourcePath);
  if (!(await lstat(sourceReal)).isDirectory()) {
    throw new Error("Backend source must be a directory");
  }
  const destinationReal = path.join(await realpath(assetsPath), path.basename(destinationPath));
  if (isWithin(destinationReal, sourceReal)) {
    throw new Error("Backend source is inside the staging destination");
  }

  for (const entry of [...BACKEND_ENTRIES, "web/dist/index.html"]) {
    const entryPath = path.join(sourceReal, entry);
    let info;
    try {
      info = await lstat(entryPath);
    } catch (error) {
      if (error.code === "ENOENT") throw new Error(`Missing backend asset: ${entry}`);
      throw error;
    }
    const expectedDirectory = BACKEND_DIRECTORY_ENTRIES.has(entry);
    if (info.isSymbolicLink() || (expectedDirectory ? !info.isDirectory() : !info.isFile())) {
      throw new Error(`Invalid backend asset: ${entry}`);
    }
    const entryReal = await realpath(entryPath);
    if (!isWithin(sourceReal, entryReal) || !isBackendFile(entry)) {
      throw new Error(`Backend asset escapes the source or is excluded: ${entry}`);
    }
    if (isWithin(destinationReal, entryReal) || (expectedDirectory && isWithin(entryReal, destinationReal))) {
      throw new Error(`Backend asset overlaps the staging destination: ${entry}`);
    }
  }

  await rm(destinationPath, { recursive: true, force: true });
  await mkdir(destinationPath, { recursive: true });
  for (const entry of BACKEND_ENTRIES) {
    await mkdir(path.dirname(path.join(destinationPath, entry)), { recursive: true });
    await cp(path.join(sourceReal, entry), path.join(destinationPath, entry), {
      recursive: true,
      filter: async candidate =>
        isBackendFile(path.relative(sourceReal, candidate)) && !(await lstat(candidate)).isSymbolicLink(),
    });
  }
  return destinationPath;
}
