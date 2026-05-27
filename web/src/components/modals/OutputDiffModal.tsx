// Side-by-side comparison of two completed runs.
//
// Useful for: did the rerun change anything? Why does run B have an extra
// artifact run A didn't? — answered by lining up the node statuses, outputs,
// and artifacts of two run records and flagging the differences.

import { useEffect, useMemo, useState } from 'react';
import { Dialog } from '../ui/Dialog';
import { apiGet, ApiError } from '../../api/client';
import { safeValidateRunRecord } from '../../api/validators';
import type { RunRecord } from '../../types';

interface OutputDiffModalProps {
  runs: RunRecord[]; // recent runs the user can pick from
  initialLeftRunId?: string;
  initialRightRunId?: string;
  onClose: () => void;
}

interface RunSummary {
  id: string;
  status: string;
  workflowName: string;
  startTime?: string;
  nodeCount: number;
  artifactCount: number;
}

function summarise(record: RunRecord | null): RunSummary | null {
  if (!record) return null;
  return {
    id: record.run_id,
    status: record.status,
    workflowName: record.workflow_name || 'Untitled',
    startTime: record.start_time,
    nodeCount: record.node_statuses?.length ?? 0,
    artifactCount: Object.keys(record.artifacts || {}).length,
  };
}

function statusChip(status: string): string {
  switch (status) {
    case 'completed': return 'diff-status diff-status-ok';
    case 'error': return 'diff-status diff-status-err';
    case 'cancelled': return 'diff-status diff-status-warn';
    case 'running': return 'diff-status diff-status-run';
    default: return 'diff-status';
  }
}

interface DiffRowProps {
  label: string;
  left: string;
  right: string;
}

function DiffRow({ label, left, right }: DiffRowProps) {
  const differ = left !== right;
  return (
    <div className={`diff-row ${differ ? 'differs' : ''}`}>
      <div className="diff-row-label">{label}</div>
      <div className="diff-cell">{left || <span className="diff-empty">—</span>}</div>
      <div className="diff-cell">{right || <span className="diff-empty">—</span>}</div>
    </div>
  );
}

export default function OutputDiffModal({ runs, initialLeftRunId, initialRightRunId, onClose }: OutputDiffModalProps) {
  const eligible = useMemo(
    () => runs.filter(r => r.status === 'completed' || r.status === 'error').slice(0, 30),
    [runs],
  );

  const [leftId, setLeftId] = useState(initialLeftRunId || eligible[0]?.run_id || '');
  const [rightId, setRightId] = useState(initialRightRunId || eligible[1]?.run_id || eligible[0]?.run_id || '');
  const [leftRecord, setLeftRecord] = useState<RunRecord | null>(null);
  const [rightRecord, setRightRecord] = useState<RunRecord | null>(null);
  const [loadingLeft, setLoadingLeft] = useState(false);
  const [loadingRight, setLoadingRight] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!leftId) { setLeftRecord(null); return; }
    let cancelled = false;
    setLoadingLeft(true);
    setError(null);
    apiGet<unknown>(`/runs/${leftId}`)
      .then(raw => {
        if (cancelled) return;
        const result = safeValidateRunRecord(raw);
        if (!result.ok) {
          setLeftRecord(null);
          setError(`Left run: ${result.error.message}`);
          return;
        }
        setLeftRecord(raw as RunRecord);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLeftRecord(null);
        setError(err instanceof ApiError ? `Left run: ${err.statusText}` : String(err));
      })
      .finally(() => { if (!cancelled) setLoadingLeft(false); });
    return () => { cancelled = true; };
  }, [leftId]);

  useEffect(() => {
    if (!rightId) { setRightRecord(null); return; }
    let cancelled = false;
    setLoadingRight(true);
    setError(null);
    apiGet<unknown>(`/runs/${rightId}`)
      .then(raw => {
        if (cancelled) return;
        const result = safeValidateRunRecord(raw);
        if (!result.ok) {
          setRightRecord(null);
          setError(`Right run: ${result.error.message}`);
          return;
        }
        setRightRecord(raw as RunRecord);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setRightRecord(null);
        setError(err instanceof ApiError ? `Right run: ${err.statusText}` : String(err));
      })
      .finally(() => { if (!cancelled) setLoadingRight(false); });
    return () => { cancelled = true; };
  }, [rightId]);

  const leftSummary = summarise(leftRecord);
  const rightSummary = summarise(rightRecord);

  // Collect the union of node ids so we can line up "node X ran here, didn't
  // there" rows even when one side has nodes the other doesn't.
  const nodeIds = useMemo(() => {
    const set = new Set<string>();
    leftRecord?.node_statuses?.forEach(s => set.add(s.node_id));
    rightRecord?.node_statuses?.forEach(s => set.add(s.node_id));
    return Array.from(set);
  }, [leftRecord, rightRecord]);

  const artifactPaths = useMemo(() => {
    const set = new Set<string>();
    Object.keys(leftRecord?.artifacts || {}).forEach(k => set.add(k));
    Object.keys(rightRecord?.artifacts || {}).forEach(k => set.add(k));
    return Array.from(set);
  }, [leftRecord, rightRecord]);

  const nodeStatusFor = (record: RunRecord | null, nodeId: string): string => {
    const status = record?.node_statuses?.find(s => s.node_id === nodeId);
    if (!status) return '';
    return String(status.status);
  };

  const renderPicker = (label: string, value: string, onChange: (id: string) => void, loading: boolean) => (
    <label className="diff-picker">
      <span className="diff-picker-label">{label}{loading ? ' (loading…)' : ''}</span>
      <select className="select-input" value={value} onChange={e => onChange(e.target.value)}>
        <option value="">— pick a run —</option>
        {eligible.map(r => (
          <option key={r.run_id} value={r.run_id}>
            {(r.workflow_name || 'Untitled').slice(0, 30)} · {r.status} · {r.run_id.slice(0, 8)}
          </option>
        ))}
      </select>
    </label>
  );

  const footer = (
    <>
      <button className="btn" type="button" onClick={onClose}>Close</button>
    </>
  );

  return (
    <Dialog
      title="Compare runs"
      width={920}
      maxHeight="85vh"
      onClose={onClose}
      footer={footer}
    >
      <div className="output-diff-controls">
        {renderPicker('Run A', leftId, setLeftId, loadingLeft)}
        {renderPicker('Run B', rightId, setRightId, loadingRight)}
      </div>

      {error && <div className="diff-error">{error}</div>}

      <div className="diff-summary">
        <div className="diff-summary-col">
          {leftSummary ? (
            <>
              <div className="diff-summary-title">{leftSummary.workflowName}</div>
              <div className={statusChip(leftSummary.status)}>{leftSummary.status}</div>
              <div className="diff-summary-meta">
                {leftSummary.nodeCount} nodes · {leftSummary.artifactCount} artifacts
                {leftSummary.startTime && <> · started {new Date(leftSummary.startTime).toLocaleString()}</>}
              </div>
            </>
          ) : <span className="diff-empty">No run selected</span>}
        </div>
        <div className="diff-summary-col">
          {rightSummary ? (
            <>
              <div className="diff-summary-title">{rightSummary.workflowName}</div>
              <div className={statusChip(rightSummary.status)}>{rightSummary.status}</div>
              <div className="diff-summary-meta">
                {rightSummary.nodeCount} nodes · {rightSummary.artifactCount} artifacts
                {rightSummary.startTime && <> · started {new Date(rightSummary.startTime).toLocaleString()}</>}
              </div>
            </>
          ) : <span className="diff-empty">No run selected</span>}
        </div>
      </div>

      <div className="diff-section">
        <div className="diff-section-title">Per-node status ({nodeIds.length})</div>
        {nodeIds.length === 0 ? <div className="diff-empty">No nodes in either run.</div> : (
          <div className="diff-table">
            {nodeIds.map(id => (
              <DiffRow
                key={`status-${id}`}
                label={id}
                left={nodeStatusFor(leftRecord, id)}
                right={nodeStatusFor(rightRecord, id)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="diff-section">
        <div className="diff-section-title">Artifacts ({artifactPaths.length})</div>
        {artifactPaths.length === 0 ? <div className="diff-empty">Neither run produced artifacts yet.</div> : (
          <div className="diff-table">
            {artifactPaths.map(path => (
              <DiffRow
                key={`artifact-${path}`}
                label={path}
                left={leftRecord?.artifacts?.[path] || ''}
                right={rightRecord?.artifacts?.[path] || ''}
              />
            ))}
          </div>
        )}
      </div>

      {leftRecord?.error || rightRecord?.error ? (
        <div className="diff-section">
          <div className="diff-section-title">Errors</div>
          <div className="diff-table">
            <DiffRow label="message" left={leftRecord?.error || ''} right={rightRecord?.error || ''} />
          </div>
        </div>
      ) : null}
    </Dialog>
  );
}
