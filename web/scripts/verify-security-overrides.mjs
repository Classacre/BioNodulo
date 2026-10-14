// Clerk v6.39 removed the unused Solana/mobile-wallet dependency chain that
// pulled native Metro tooling (and vulnerable braces) into this browser app.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Clerk } from '@clerk/clerk-js';

assert.equal(typeof Clerk, 'function');
assert.throws(() => new Clerk('invalid'), /publishableKey.*invalid/);

const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
const removed = ['@solana/web3.js', '@solana/wallet-adapter-react', 'react-native', 'metro'];
for (const name of removed) {
  assert.equal(Object.entries(lock.packages).some(([path, entry]) =>
    !entry.dev && (path === `node_modules/${name}` || path.endsWith(`/node_modules/${name}`))), false,
  `Unused native wallet dependency ${name} must not return to the production tree`);
}
console.log('Clerk imports and validates publishable keys; the unused Solana/React Native/Metro production tree is absent. No external request was made.');
// The browser SDK installs background timers even when key validation throws.
// Every assertion above is synchronous; end this standalone Node smoke check.
process.exit(0);
