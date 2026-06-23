import { describe, it, expect } from 'vitest';
import {
  mapCloudRunStatus,
  isTerminalCloudStatus,
  deriveCloudNodeStatuses,
  buildCloudNodeStatuses,
  nodeIdFromTag,
  stripNodeTag,
} from '../utils/cloudRunStatus';

// Build a worker-shaped log blob: each line "[<iso>] <LEVEL>: <message>".
function line(message: string, level = 'INFO'): string {
  return `[2026-06-16T00:00:00Z] ${level}: ${message}`;
}

describe('mapCloudRunStatus', () => {
  it('maps coarse cloud statuses onto the RunRecord union', () => {
    expect(mapCloudRunStatus('queued')).toBe('pending');
    expect(mapCloudRunStatus('running')).toBe('running');
    expect(mapCloudRunStatus('completed')).toBe('completed');
    expect(mapCloudRunStatus('cancelled')).toBe('cancelled');
    expect(mapCloudRunStatus('failed')).toBe('error');
    expect(mapCloudRunStatus('interrupted')).toBe('error');
    expect(mapCloudRunStatus('weird')).toBe('running');
  });
});

describe('isTerminalCloudStatus', () => {
  it('treats completed/failed/cancelled/interrupted as terminal', () => {
    expect(isTerminalCloudStatus('completed')).toBe(true);
    expect(isTerminalCloudStatus('failed')).toBe(true);
    expect(isTerminalCloudStatus('cancelled')).toBe(true);
    expect(isTerminalCloudStatus('interrupted')).toBe(true);
    expect(isTerminalCloudStatus('running')).toBe(false);
    expect(isTerminalCloudStatus('queued')).toBe(false);
  });
});

describe('node tag parsing', () => {
  it('extracts and strips the [node:<id>] marker', () => {
    expect(nodeIdFromTag('node Foo started [node:abc-1]')).toBe('abc-1');
    expect(nodeIdFromTag('no marker here')).toBeNull();
    expect(stripNodeTag('node Foo started [node:abc-1]')).toBe('node Foo started');
    expect(stripNodeTag('plain line')).toBe('plain line');
  });

  it('handles ids containing colons or dashes', () => {
    expect(nodeIdFromTag('node X completed [node:wf:1:node-2]')).toBe('wf:1:node-2');
  });
});

describe('deriveCloudNodeStatuses', () => {
  it('returns empty for empty logs', () => {
    expect(deriveCloudNodeStatuses('').size).toBe(0);
  });

  it('marks a started node running and a completed node completed', () => {
    const blob = [
      line('node Align started [node:n1]'),
      line('node Align completed [node:n1]'),
      line('node Count started [node:n2]'),
    ].join('\n');
    const m = deriveCloudNodeStatuses(blob);
    expect(m.get('n1')).toBe('completed');
    expect(m.get('n2')).toBe('running');
  });

  it('maps cache hit and skip/bypass onto cached/skipped', () => {
    const blob = [
      line('node A cache hit [node:a]'),
      line('node B skipped [node:b]'),
      line('node C bypassed [node:c]'),
    ].join('\n');
    const m = deriveCloudNodeStatuses(blob);
    expect(m.get('a')).toBe('cached');
    expect(m.get('b')).toBe('skipped');
    expect(m.get('c')).toBe('skipped');
  });

  it('records a node error from an ERROR-level tagged line', () => {
    const blob = [
      line('node D started [node:d]'),
      line('boom: traceback [node:d]', 'ERROR'),
    ].join('\n');
    expect(deriveCloudNodeStatuses(blob).get('d')).toBe('error');
  });

  it('does not downgrade a settled node back to running', () => {
    const blob = [
      line('node E started [node:e]'),
      line('node E completed [node:e]'),
      line('node E started [node:e]'), // stray re-emit
    ].join('\n');
    expect(deriveCloudNodeStatuses(blob).get('e')).toBe('completed');
  });

  it('ignores untagged lines', () => {
    const blob = [
      line('Installing 12 dependencies'),
      line('run started (2 nodes)'),
    ].join('\n');
    expect(deriveCloudNodeStatuses(blob).size).toBe(0);
  });
});

describe('buildCloudNodeStatuses', () => {
  const plan = ['n1', 'n2', 'n3'];

  it('overlays derived statuses on a pending baseline while running', () => {
    const derived = new Map<string, 'running' | 'completed'>([['n1', 'completed'], ['n2', 'running']]);
    const out = buildCloudNodeStatuses(plan, derived, 'running');
    expect(out).toEqual([
      { node_id: 'n1', status: 'completed' },
      { node_id: 'n2', status: 'running' },
      { node_id: 'n3', status: 'pending' },
    ]);
  });

  it('promotes unseen nodes to completed on terminal success', () => {
    const derived = new Map<string, 'cached'>([['n1', 'cached']]);
    const out = buildCloudNodeStatuses(plan, derived, 'completed');
    expect(out.map(n => n.status)).toEqual(['cached', 'completed', 'completed']);
  });

  it('turns still-running nodes into errors on failure and attaches the message', () => {
    const derived = new Map<string, 'completed' | 'running'>([['n1', 'completed'], ['n2', 'running']]);
    const out = buildCloudNodeStatuses(plan, derived, 'error', 'kaboom');
    expect(out[0]).toEqual({ node_id: 'n1', status: 'completed' });
    expect(out[1]).toEqual({ node_id: 'n2', status: 'error', error: 'kaboom' });
    expect(out[2]).toEqual({ node_id: 'n3', status: 'pending' });
  });
});
