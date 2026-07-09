import { describe, it, expect } from 'vitest';
import { buildCloudLandingUrl } from '../collab/shareLinks';

describe('buildCloudLandingUrl', () => {
  it('builds a fragment-based cloud landing link', () => {
    const u = buildCloudLandingUrl({ cloudHost: 'https://cloud.bionodulo.com', tunnelBase: 'https://x.trycloudflare.com', workflowId: 'wf1', inviteToken: 'tok' });
    expect(u).toBe('https://cloud.bionodulo.com/j#h=https%3A%2F%2Fx.trycloudflare.com&w=wf1&i=tok');
  });
});
