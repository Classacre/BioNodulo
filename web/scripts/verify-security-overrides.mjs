// Exercise the actual parent APIs affected by the bounded transitive updates.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { Connection } = require('@solana/web3.js');
const connection = new Connection('https://example.invalid', {
  fetch: async (_url, options) => {
    const request = JSON.parse(options.body);
    assert.equal(request.method, 'getLatestBlockhash');
    assert.equal(typeof request.id, 'string');
    return new Response(JSON.stringify({
      jsonrpc: '2.0', id: request.id,
      result: { context: { slot: 1 }, value: { blockhash: '11111111111111111111111111111111', lastValidBlockHeight: 10 } },
    }), { status: 200, headers: { 'content-type': 'application/json' } });
  },
});
assert.deepEqual(await connection.getLatestBlockhash(), {
  blockhash: '11111111111111111111111111111111', lastValidBlockHeight: 10,
});

const metroEntry = require.resolve('metro');
const { getAssetSize } = require(path.join(path.dirname(metroEntry), 'Assets.js'));
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2ioAAAAASUVORK5CYII=', 'base64');
assert.deepEqual(getAssetSize('png', png, 'fixture.png'), { width: 1, height: 1 });
assert.equal(getAssetSize('txt', Buffer.from('text'), 'fixture.txt'), null);
assert.throws(() => getAssetSize('png', Buffer.alloc(0), 'empty.png'), /cannot be an empty file/);
console.log('Solana HTTP RPC and Metro image parsing pass with the security overrides. No external request was made.');
