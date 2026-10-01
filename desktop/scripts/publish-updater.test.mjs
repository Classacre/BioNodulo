import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash, generateKeyPairSync, sign } from 'node:crypto';
import { assetFingerprint, buildManifest, checkSignature, payloads } from './publish-updater.mjs';

const repository = 'Classacre/BioNodulo';
const version = '0.1.1-alpha.8';
const { privateKey, publicKey } = generateKeyPairSync('ed25519');
const keyId = Buffer.from('0123456789abcdef', 'hex');
const keyBytes = Buffer.concat([Buffer.from('Ed'), keyId, publicKey.export({ format: 'der', type: 'spki' }).subarray(-32)]);
const key = Buffer.from(`untrusted comment: test key\n${keyBytes.toString('base64')}\n`).toString('base64');

function signed(payload, comment = 'timestamp:1790820000\tfile:test') {
  const hash = createHash('blake2b512').update(payload).digest();
  const raw = sign(null, hash, privateKey);
  const body = Buffer.concat([Buffer.from('ED'), keyId, raw]);
  const global = sign(null, Buffer.concat([raw, Buffer.from(comment)]), privateKey);
  return { hash, signature: Buffer.from(`untrusted comment: test signature\n${body.toString('base64')}\ntrusted comment: ${comment}\n${global.toString('base64')}\n`).toString('base64') };
}
function fixture() {
  let id = 1;
  const assets = [];
  const verified = new Map();
  const add = (name, bytes, digest) => assets.push({ name, id: id++, size: bytes, digest, state: 'uploaded', browser_download_url: `https://github.com/${repository}/releases/download/desktop-v${version}/${name}` });
  for (const { name } of payloads(version)) {
    const payload = Buffer.from(`binary fixture:${name}`);
    const { signature, hash } = signed(payload);
    checkSignature(signature, key, hash);
    const sha256 = createHash('sha256').update(payload).digest('hex');
    add(name, payload.length, `sha256:${sha256}`);
    add(`${name}.sig`, Buffer.byteLength(signature), 'sha256:signature');
    verified.set(name, { signature, sha256, bytes: payload.length, verified: true });
  }
  add(`BioNodulo_${version}_aarch64.dmg`, 100, 'sha256:dmg-arm');
  add(`BioNodulo_${version}_x64.dmg`, 100, 'sha256:dmg-intel');
  return { release: { tag_name: `desktop-v${version}`, created_at: '2026-10-01T00:00:00Z', body: 'Release notes', assets }, verified };
}

test('assembles every platform and installer alias from verified existing assets', () => {
  const { release, verified } = fixture();
  const manifest = buildManifest(release, repository, version, verified);
  assert.equal(manifest.version, version);
  assert.equal(Object.keys(manifest.platforms).length, 9);
  assert.equal(manifest.platforms['linux-x86_64'].url, manifest.platforms['linux-x86_64-appimage'].url);
  assert.match(manifest.platforms['linux-x86_64-deb'].url, /\.deb$/);
  assert.equal(manifest.platforms['windows-x86_64'].signature, verified.get(`BioNodulo_${version}_x64-setup.exe`).signature);
});
test('refuses partial builds rather than publishing an incomplete updater', () => {
  const { release, verified } = fixture();
  release.assets = release.assets.filter((asset) => !asset.name.endsWith('_x64.dmg'));
  assert.throws(() => buildManifest(release, repository, version, verified), /Missing completed asset/);
});
test('rejects payload digest, size, signature proof and release URL mismatches', () => {
  for (const change of ['digest', 'size', 'proof', 'url']) {
    const { release, verified } = fixture();
    const asset = release.assets[0];
    if (change === 'digest') asset.digest = 'sha256:wrong';
    if (change === 'size') asset.size++;
    if (change === 'proof') verified.get(asset.name).verified = false;
    if (change === 'url') asset.browser_download_url = 'https://example.org/fake';
    assert.throws(() => buildManifest(release, repository, version, verified), /Unverified payload|Unexpected payload URL/);
  }
});
test('detects tampered payloads and trusted comments', () => {
  const payload = Buffer.from('original installer');
  const { signature } = signed(payload);
  assert.throws(() => checkSignature(signature, key, createHash('blake2b512').update('tampered installer').digest()), /verification failed/);
  const tampered = Buffer.from(Buffer.from(signature, 'base64').toString().replace('file:test', 'file:fake')).toString('base64');
  assert.throws(() => checkSignature(tampered, key, createHash('blake2b512').update(payload).digest()), /verification failed/);
});
test('rejects another key and malformed encodings', () => {
  const { signature, hash } = signed(Buffer.from('payload'));
  const otherKeyBytes = Buffer.from(keyBytes);
  otherKeyBytes[2] ^= 1;
  const otherKey = Buffer.from(`untrusted comment: other\n${otherKeyBytes.toString('base64')}\n`).toString('base64');
  assert.throws(() => checkSignature(signature, otherKey, hash), /key mismatch/);
  assert.throws(() => checkSignature('not a signature!', key, hash), /Invalid base64/);
});
test('fingerprints preserve installers while allowing manifest-only repair', () => {
  const { release } = fixture();
  const before = assetFingerprint(release.assets);
  const after = [...release.assets, { id: 50, name: 'latest.json', size: 3000, digest: 'sha256:new' }];
  assert.equal(assetFingerprint(after), before);
  after[0] = { ...after[0], id: 999 };
  assert.notEqual(assetFingerprint(after), before);
});
