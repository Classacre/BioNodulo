// Bulk parameter editor.
//
// When the user has multiple nodes selected, this modal surfaces every
// parameter key that exists on *every* selected node (intersection, not
// union — applying a value to a node that doesn't expose the key would
// silently no-op or, worse, introduce a stray field), shows the current
// values (with "[varies]" when they disagree), and lets a single edit
// fan out across the whole selection.
//
// We deliberately omit the per-spec widget rendering and use a plain text
// input — the canvas's DOM-widget overlay already handles type-aware UI
// when editing one node at a time, and the bulk path is for quick
// "set --threads 8 across these 6 aligners" jobs where a text input is
// good enough.

import { useMemo, useState } from 'react';
import { Dialog } from '../ui/Dialog';
import type { WorkflowNode } from '../../types';

interface BulkParamModalProps {
  nodes: WorkflowNode[];                            // the selected nodes
  onApply: (changes: Array<{ key: string; value: unknown }>) => void;
  onClose: () => void;
}

interface SharedParam {
  key: string;
  /** All current values present in the selection. */
  values: unknown[];
  varies: boolean;
}

function describeValue(value: unknown): string {
  if (value === undefined || value === null || value === '') return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function coerce(input: string, sample: unknown): unknown {
  // Use the first sample's type as a hint so we round-trip ints / floats /
  // booleans correctly. Falls back to the raw string.
  if (typeof sample === 'number') {
    const n = Number(input);
    if (Number.isFinite(n)) return n;
  }
  if (typeof sample === 'boolean') {
    if (input === 'true' || input === '1') return true;
    if (input === 'false' || input === '0') return false;
  }
  return input;
}

export default function BulkParamModal({ nodes, onApply, onClose }: BulkParamModalProps) {
  const shared = useMemo<SharedParam[]>(() => {
    if (nodes.length === 0) return [];
    const keysPerNode = nodes.map(n => new Set(Object.keys(n.params || {})));
    const intersect = Array.from(keysPerNode[0]).filter(key => keysPerNode.every(set => set.has(key))).sort();
    return intersect.map(key => {
      const values = nodes.map(n => n.params?.[key]);
      const varies = values.some(value => describeValue(value) !== describeValue(values[0]));
      return { key, values, varies };
    });
  }, [nodes]);

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Set<string>>(new Set());

  const handleChange = (key: string, value: string) => {
    setDrafts(prev => ({ ...prev, [key]: value }));
    setTouched(prev => {
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });
  };

  const apply = () => {
    const changes: Array<{ key: string; value: unknown }> = [];
    for (const param of shared) {
      if (!touched.has(param.key)) continue;
      const sample = param.values[0];
      changes.push({ key: param.key, value: coerce(drafts[param.key] ?? '', sample) });
    }
    onApply(changes);
    onClose();
  };

  const footer = (
    <>
      <button className="btn" type="button" onClick={onClose}>Cancel</button>
      <button className="btn btn-primary" type="button" onClick={apply} disabled={touched.size === 0}>
        Apply to {nodes.length} node{nodes.length === 1 ? '' : 's'}
      </button>
    </>
  );

  return (
    <Dialog
      title="Bulk parameter edit"
      width={620}
      onClose={onClose}
      footer={footer}
      header={
        <span>
          Editing parameters shared by <strong>{nodes.length}</strong> selected node{nodes.length === 1 ? '' : 's'}.
          {shared.length === 0 && ' No parameters are common to every selected node.'}
        </span>
      }
    >
      {shared.length === 0 ? (
        <div style={{ color: 'var(--muted)', fontSize: 12, padding: '12px 0' }}>
          The selected nodes don't share any parameter keys. Pick nodes of the same
          type (or a compatible subset) to bulk-edit.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {shared.map(param => {
            const placeholder = param.varies ? '[varies]' : describeValue(param.values[0]);
            const draft = drafts[param.key] ?? '';
            return (
              <label key={param.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <code style={{ minWidth: 140, fontSize: 12, color: 'var(--text)' }}>{param.key}</code>
                <input
                  type="text"
                  className="text-input"
                  value={draft}
                  placeholder={placeholder}
                  onChange={e => handleChange(param.key, e.target.value)}
                  style={{ flex: 1 }}
                />
                {touched.has(param.key) && (
                  <button
                    type="button"
                    className="btn btn-icon btn-sm"
                    onClick={() => {
                      setDrafts(prev => { const next = { ...prev }; delete next[param.key]; return next; });
                      setTouched(prev => { const next = new Set(prev); next.delete(param.key); return next; });
                    }}
                    title="Don't change this parameter"
                  >×</button>
                )}
              </label>
            );
          })}
        </div>
      )}
    </Dialog>
  );
}
