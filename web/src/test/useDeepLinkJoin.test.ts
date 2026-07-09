import { deepLinkToJoin, isValidRemoteBase } from '../hooks/collab/useDeepLinkJoin';

describe('deepLinkToJoin', () => {
  it('maps an open deep link with a tunnel host to a remote join', () => {
    expect(deepLinkToJoin({ host: 'open', path: '/', params: { h: 'https://x.trycloudflare.com', w: 'wf1', i: 'tok' } }))
      .toEqual({ remoteBase: 'https://x.trycloudflare.com', target: { workflowId: 'wf1', inviteToken: 'tok' } });
    expect(deepLinkToJoin({ host: 'desktop-auth', path: '/', params: {} })).toBeNull();
  });

  it('returns null when params.w is missing', () => {
    expect(deepLinkToJoin({ host: 'open', path: '/', params: { h: 'https://x.trycloudflare.com' } })).toBeNull();
  });

  it('sets inviteToken to null when params.i is absent', () => {
    expect(deepLinkToJoin({ host: 'open', path: '/', params: { h: 'https://x.trycloudflare.com', w: 'wf2' } }))
      .toEqual({ remoteBase: 'https://x.trycloudflare.com', target: { workflowId: 'wf2', inviteToken: null } });
  });
});

describe('isValidRemoteBase', () => {
  it('accepts https trycloudflare.com hosts', () => {
    expect(isValidRemoteBase('https://x.trycloudflare.com')).toBe(true);
    expect(isValidRemoteBase('https://abc-def.trycloudflare.com')).toBe(true);
  });

  it('rejects http', () => {
    expect(isValidRemoteBase('http://x.trycloudflare.com')).toBe(false);
  });

  it('rejects non-trycloudflare hosts', () => {
    expect(isValidRemoteBase('https://evil.com')).toBe(false);
    expect(isValidRemoteBase('https://trycloudflare.com.evil.com')).toBe(false);
  });

  it('rejects null', () => {
    expect(isValidRemoteBase(null)).toBe(false);
  });
});
