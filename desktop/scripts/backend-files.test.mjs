import assert from "node:assert/strict";
import { lstat, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { BACKEND_DIRECTORY_ENTRIES, BACKEND_ENTRIES, stageBackend } from "./backend-files.mjs";

async function write(source, name) {
  const target = path.join(source, name);
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, name);
}

async function fixture(t) {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "bionodulo-staging-"));
  t.after(async () => {
    assert.equal(path.dirname(temporaryRoot), os.tmpdir());
    await rm(temporaryRoot, { recursive: true, force: true });
  });
  const source = path.join(temporaryRoot, "source");
  const assets = path.join(temporaryRoot, "assets");
  const destination = path.join(assets, "bionodulo-backend");
  await mkdir(assets);
  for (const entry of BACKEND_ENTRIES) {
    if (BACKEND_DIRECTORY_ENTRIES.has(entry)) await mkdir(path.join(source, entry), { recursive: true });
    else await write(source, entry);
  }
  await write(source, "web/dist/index.html");
  return { source, assets, destination };
}

test("staging preserves runtime assets and excludes local state", async t => {
  const { source, assets, destination } = await fixture(t);
  const nestedRequired = [
    "bionodulo/nodes/generated/biotools_catalog.sqlite.gz",
    "bionodulo/environments/locks/tool/pixi.lock",
    "bionodulo/ai/bundled_skills/example/SKILL.md",
    "web/dist/index.html", "templates/data/smoke/reads.fastq",
    "templates/workflow.json", "docs/help/getting-started.md",
    "examples/workflows/example.json",
  ];
  const required = [
    ...BACKEND_ENTRIES.filter(entry => !BACKEND_DIRECTORY_ENTRIES.has(entry)),
    ...nestedRequired,
  ];
  const excluded = [
    ".env.local", "runs/run-1/result.json", "workspace/collab.db",
    "best_so_far/best.json", "reports/private.json", "docs/plan.md",
    "web/src/App.tsx", "web/node_modules/dependency/index.js",
    "data/private.csv", "bionodulo/__pycache__/module.pyc", "bionodulo/.env",
    "bionodulo/environments/locks/tool/.pixi/envs/default/bin/python",
  ];
  for (const name of [...nestedRequired, ...excluded]) await write(source, name);
  await write(destination, "stale.txt");

  assert.equal(await stageBackend(source, destination, assets), destination);
  for (const name of required) {
    assert.equal(await readFile(path.join(destination, name), "utf8"), name);
  }
  for (const name of [...excluded, "stale.txt"]) {
    await assert.rejects(readFile(path.join(destination, name)), { code: "ENOENT" });
  }
});

test("missing required input preserves an existing stage", async t => {
  const { source, assets, destination } = await fixture(t);
  await write(destination, "keep.txt");
  await rm(path.join(source, "web", "dist", "index.html"));
  await assert.rejects(stageBackend(source, destination, assets), /Missing backend asset: web\/dist\/index\.html/);
  assert.equal(await readFile(path.join(destination, "keep.txt"), "utf8"), "keep.txt");
});

test("source inside the stage is rejected before removal", async t => {
  const { assets, destination } = await fixture(t);
  await write(destination, "nested/keep.txt");
  for (const source of [destination, path.join(destination, "nested")]) {
    await assert.rejects(stageBackend(source, destination, assets), /source is inside the staging destination/);
    assert.equal(await readFile(path.join(destination, "nested", "keep.txt"), "utf8"), "nested/keep.txt");
  }
});

test("destination outside the assets root is rejected before removal", async t => {
  const { source, assets, destination } = await fixture(t);
  await write(destination, "keep.txt");
  await assert.rejects(stageBackend(source, path.join(source, "bionodulo-backend"), assets), /destination must be/);
  assert.equal(await readFile(path.join(destination, "keep.txt"), "utf8"), "keep.txt");
});

test("every declared input exists in this checkout", async () => {
  const repo = fileURLToPath(new URL("../../", import.meta.url));
  // web/dist is built for packaging and may be absent from a clean checkout.
  for (const entry of BACKEND_ENTRIES) {
    if (entry === "web/dist") continue;
    const target = path.join(repo, entry);
    const info = await lstat(target);
    assert.ok(BACKEND_DIRECTORY_ENTRIES.has(entry) ? info.isDirectory() : info.isFile(), entry);
  }
  assert.ok((await readdir(path.join(repo, "web"))).includes("package.json"));
});
