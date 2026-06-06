import { describe, expect, it } from 'vitest';
import { redactSecrets } from '../utils/redaction';

describe('frontend redaction helpers', () => {
  it('masks nested secret-like values before browser rendering', () => {
    const redacted = redactSecrets({
      api_key: 'secret-key',
      safe: 'visible',
      nested: {
        Authorization: 'Bearer secret-token',
        items: [
          { password: 'secret-password' },
          'plain',
        ],
      },
    });

    expect(redacted).toEqual({
      api_key: '***',
      safe: 'visible',
      nested: {
        Authorization: '***',
        items: [
          { password: '***' },
          'plain',
        ],
      },
    });
    expect(JSON.stringify(redacted)).not.toContain('secret-key');
    expect(JSON.stringify(redacted)).not.toContain('secret-token');
    expect(JSON.stringify(redacted)).not.toContain('secret-password');
  });

  it('masks secret-like scalar arrays without mutating the original payload', () => {
    const payload = {
      headers: [{ token: 'secret-token' }],
      values: ['visible'],
    };

    const redacted = redactSecrets(payload);

    expect(redacted).toEqual({
      headers: [{ token: '***' }],
      values: ['visible'],
    });
    expect(payload.headers[0]?.token).toBe('secret-token');
  });
});
