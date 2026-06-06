const REDACTED = '***';

const SECRET_KEY_PARTS = [
  'apikey',
  'api_key',
  'authorization',
  'bearer',
  'client_secret',
  'credential',
  'key',
  'password',
  'secret',
  'token',
];

function isSecretKey(key: unknown): boolean {
  const normalized = String(key ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '_');
  return SECRET_KEY_PARTS.some(part => normalized.includes(part));
}

export function redactSecrets(value: unknown, parentKey: unknown = ''): unknown {
  if (isSecretKey(parentKey)) return REDACTED;
  if (Array.isArray(value)) return value.map(item => redactSecrets(item, parentKey));
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, redactSecrets(item, key)]),
    );
  }
  return value;
}
