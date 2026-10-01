/** Publish one complete updater manifest after every platform build finishes. */
import { createHash, createPublicKey, verify } from 'node:crypto';
import { execFileSync, spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync, unlinkSync, rmdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptPath = fileURLToPath(import.meta.url);
const root = resolve(dirname(scriptPath), '../..');
const PUBLIC_KEY_PREFIX = Buffer.from('302a300506032b6570032100', 'hex');

function decode(value) {
  if (typeof value !== 'string') throw new Error('Expected encoded signature');
  const text = value.replace(/\s/g, '');
  const bytes = Buffer.from(text, 'base64');
  if (bytes.toString('base64') !== text) throw new Error('Invalid base64');
  return bytes;
}

export function checkSignature(encoded, publicKey, payloadHash) {
  const keyLines = decode(publicKey).toString('utf8').trimEnd().split('\n');
  const key = decode(keyLines[1]);
  const lines = decode(encoded).toString('utf8').trimEnd().split('\n');
  const signature = decode(lines[1]);
  if (key.length !== 42 || signature.length !== 74 || signature.subarray(0, 2).toString() !== 'ED'
      || !signature.subarray(2, 10).equals(key.subarray(2, 10))
      || !lines[2]?.startsWith('trusted comment: ')) throw new Error('Signature format or key mismatch');
  const verifier = createPublicKey({ key: Buffer.concat([PUBLIC_KEY_PREFIX, key.subarray(10)]), format: 'der', type: 'spki' });
  const rawSignature = signature.subarray(10);
  if (!verify(null, payloadHash, verifier, rawSignature)
      || !verify(null, Buffer.concat([rawSignature, Buffer.from(lines[2].slice('trusted comment: '.length))]), verifier, decode(lines[3]))) {
    throw new Error('Updater signature verification failed');
  }
}

export function payloads(version) {
  if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(version)) throw new Error('Invalid release version');
  return [
    { name: 'BioNodulo_aarch64.app.tar.gz', platforms: ['darwin-aarch64', 'darwin-aarch64-app'] },
    { name: 'BioNodulo_x64.app.tar.gz', platforms: ['darwin-x86_64', 'darwin-x86_64-app'] },
    { name: `BioNodulo_${version}_x64-setup.exe`, platforms: ['windows-x86_64', 'windows-x86_64-nsis'] },
    { name: `BioNodulo_${version}_amd64.AppImage`, platforms: ['linux-x86_64', 'linux-x86_64-appimage'] },
    { name: `BioNodulo_${version}_amd64.deb`, platforms: ['linux-x86_64-deb'] },
  ];
}

export function assetFingerprint(assets) {
  return JSON.stringify(assets.filter((asset) => asset.name !== 'latest.json')
    .map(({ id, name, size, digest }) => ({ id, name, size, digest })).sort((a, b) => a.name.localeCompare(b.name)));
}

export function buildManifest(release, repository, version, verified) {
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository) || release.tag_name !== `desktop-v${version}`) throw new Error('Release identity mismatch');
  const assets = new Map(release.assets.map((asset) => [asset.name, asset]));
  if (assets.size !== release.assets.length) throw new Error('Ambiguous release assets');
  const required = [...payloads(version).flatMap(({ name }) => [name, `${name}.sig`]),
    `BioNodulo_${version}_aarch64.dmg`, `BioNodulo_${version}_x64.dmg`];
  for (const name of required) {
    const asset = assets.get(name);
    if (!asset || asset.state !== 'uploaded' || !(asset.size > 0)) throw new Error(`Missing completed asset: ${name}`);
  }
  const platforms = {};
  for (const { name, platforms: aliases } of payloads(version)) {
    const proof = verified.get(name);
    const asset = assets.get(name);
    if (!proof?.verified || `sha256:${proof.sha256}` !== asset.digest || proof.bytes !== asset.size) throw new Error(`Unverified payload: ${name}`);
    const url = `https://github.com/${repository}/releases/download/${release.tag_name}/${encodeURIComponent(name)}`;
    if (asset.browser_download_url !== url) throw new Error(`Unexpected payload URL: ${name}`);
    for (const alias of aliases) platforms[alias] = { signature: proof.signature, url };
  }
  if (!Number.isFinite(Date.parse(release.published_at ?? release.created_at))) throw new Error('Invalid release date');
  return { version, notes: release.body ?? '', pub_date: release.published_at ?? release.created_at, platforms };
}

function gh(args, options = {}) {
  return execFileSync('gh', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...options });
}
function api(path) { return JSON.parse(gh(['api', path])); }
function optionalApi(path) {
  try { return api(path); } catch (error) {
    if (/HTTP 404/.test(String(error.stderr))) return null;
    throw error;
  }
}
function resolveTag(repository, tag) {
  let object = optionalApi(`repos/${repository}/git/ref/tags/${encodeURIComponent(tag)}`)?.object;
  for (let i = 0; object?.type === 'tag' && i < 8; i++) object = api(`repos/${repository}/git/tags/${object.sha}`).object;
  if (object && object.type !== 'commit') throw new Error('Release tag does not resolve to a commit');
  return object?.sha;
}
async function streamDigest(repository, asset) {
  const child = spawn('gh', ['api', `repos/${repository}/releases/assets/${asset.id}`, '-H', 'Accept: application/octet-stream'], { stdio: ['ignore', 'pipe', 'pipe'] });
  const completion = new Promise((resolveExit, reject) => {
    child.once('error', reject);
    child.once('close', (code) => code === 0 ? resolveExit() : reject(new Error(`Artifact download failed: ${asset.name}`)));
  });
  // Drain diagnostic output; never log authentication material.
  child.stderr.resume();
  const sha = createHash('sha256');
  const signingHash = createHash('blake2b512');
  let bytes = 0;
  await Promise.all([completion, (async () => {
    for await (const chunk of child.stdout) { bytes += chunk.length; sha.update(chunk); signingHash.update(chunk); }
  })()]);
  return { bytes, sha256: sha.digest('hex'), signingHash: signingHash.digest() };
}

async function main() {
  const args = process.argv.slice(2);
  const option = (name) => args[args.indexOf(name) + 1];
  const repository = process.env.GITHUB_REPOSITORY ?? 'Classacre/BioNodulo';
  const config = JSON.parse(readFileSync(join(root, 'desktop/src-tauri/tauri.conf.json'), 'utf8'));
  const version = args.includes('--version') ? option('--version') : config.version;
  const tag = args.includes('--tag') ? option('--tag') : `desktop-v${version}`;
  const source = args.includes('--source') ? option('--source') : (process.env.GITHUB_SHA ?? execFileSync('git', ['-C', root, 'rev-parse', 'HEAD'], { encoding: 'utf8' }));
  const expectedSource = source.trim();
  if (!/^[0-9a-f]{40}$/.test(expectedSource) || tag !== `desktop-v${version}` || !/^[\w.-]+\/[\w.-]+$/.test(repository)) throw new Error('Invalid release inputs');
  const tagSource = resolveTag(repository, tag);
  if (tagSource && tagSource !== expectedSource) throw new Error('Release tag source differs from this build');
  const release = optionalApi(`repos/${repository}/releases/tags/${encodeURIComponent(tag)}`);
  const verifyOnly = args.includes('--verify-only');
  if (!verifyOnly && release && !release.draft) throw new Error('Published installers are immutable; do not rebuild an existing published release');
  if (args.includes('--check-source')) { console.log('Release source and publication state are safe for platform builds.'); return; }
  if (!release || !tagSource || release.prerelease) throw new Error('Expected completed draft release is unavailable');
  const fingerprint = assetFingerprint(release.assets);
  const verified = new Map();
  for (const { name } of payloads(version)) {
    const asset = release.assets.find((entry) => entry.name === name);
    const signatureAsset = release.assets.find((entry) => entry.name === `${name}.sig`);
    if (!asset || !signatureAsset) throw new Error(`Missing signed payload: ${name}`);
    const signature = gh(['api', `repos/${repository}/releases/assets/${signatureAsset.id}`, '-H', 'Accept: application/octet-stream']).trim();
    const proof = await streamDigest(repository, asset);
    checkSignature(signature, config.plugins.updater.pubkey, proof.signingHash);
    verified.set(name, { ...proof, signature, verified: true });
  }
  const manifest = buildManifest(release, repository, version, verified);
  const bytes = JSON.stringify(manifest, null, 2) + '\n';
  if (verifyOnly) { console.log(JSON.stringify({ tag, source: expectedSource, verifiedPayloads: verified.size, platforms: Object.keys(manifest.platforms).length, published: false })); return; }
  const staging = mkdtempSync(join(tmpdir(), 'bionodulo-updater-'));
  const path = join(staging, 'latest.json');
  try {
    writeFileSync(path, bytes);
    gh(['release', 'upload', tag, path, '--repo', repository, '--clobber']);
    const after = api(`repos/${repository}/releases/tags/${encodeURIComponent(tag)}`);
    if (assetFingerprint(after.assets) !== fingerprint) throw new Error('Installer assets changed during manifest publication');
    const latest = after.assets.find((asset) => asset.name === 'latest.json');
    if (!latest || gh(['api', `repos/${repository}/releases/assets/${latest.id}`, '-H', 'Accept: application/octet-stream']) !== bytes) throw new Error('Uploaded manifest differs from the reviewed manifest');
    gh(['release', 'edit', tag, '--repo', repository, '--draft=false', '--latest']);
    const published = api(`repos/${repository}/releases/tags/${encodeURIComponent(tag)}`);
    if (published.draft || published.prerelease || assetFingerprint(published.assets) !== fingerprint
        || resolveTag(repository, tag) !== expectedSource) throw new Error('Final release publication verification failed');
    console.log(JSON.stringify({ tag, source: expectedSource, verifiedPayloads: verified.size, platforms: Object.keys(manifest.platforms).length, published: true }));
  } finally { if (existsSync(path)) unlinkSync(path); rmdirSync(staging); }
}

if (process.argv[1] && resolve(process.argv[1]) === scriptPath) main().catch((error) => { console.error(error.message); process.exitCode = 1; });
