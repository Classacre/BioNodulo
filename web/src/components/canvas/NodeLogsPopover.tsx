// Per-node log viewer: a floating, scrollable panel anchored near the node it
// belongs to, opened from the node's right-click menu.
//
// The console shows every line for the whole workflow, which is the wrong grain
// when you are looking at one node that failed. This filters to that node and
// puts the lines next to it, so you keep the canvas context you were already
// looking at.

import { useEffect, useMemo, useRef } from 'react';
import { useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';
import { logsAtom } from '../../state/runAtoms';
import Icon from '../ui/Icon';
import type { LogEntry } from '../../types';

export interface NodeLogsPopoverProps {
  nodeId: string;
  /** Node title for the header; falls back to the id. */
  title?: string;
  /** Viewport position to anchor near, in screen pixels. */
  x: number;
  y: number;
  onClose: () => void;
}

/** Panel size, also used to keep it inside the viewport. */
const WIDTH = 460;
const MAX_HEIGHT = 320;
const MARGIN = 12;

export default function NodeLogsPopover({
  nodeId,
  title,
  x,
  y,
  onClose,
}: NodeLogsPopoverProps) {
  const { t } = useTranslation();
  const logs = useAtomValue(logsAtom);
  const bodyRef = useRef<HTMLDivElement>(null);

  const nodeLogs = useMemo(
    () => (logs as LogEntry[]).filter(entry => entry.node_id === nodeId),
    [logs, nodeId]
  );

  // Follow the tail: a running node appends, and the interesting line is the
  // newest one. Scrolling up to read history still works -- this only fires
  // when the set of lines changes.
  useEffect(() => {
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
  }, [nodeLogs.length]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Clamp into the viewport so a node near the right or bottom edge does not
  // open a panel that is half off-screen.
  const left = Math.min(Math.max(MARGIN, x), window.innerWidth - WIDTH - MARGIN);
  const top = Math.min(Math.max(MARGIN, y), window.innerHeight - MAX_HEIGHT - MARGIN);

  return (
    <div
      className="node-logs-popover"
      style={{ left, top, width: WIDTH, maxHeight: MAX_HEIGHT }}
      role="dialog"
      aria-label={t('canvas.nodeLogs.title', { defaultValue: 'Node logs' })}
      onMouseDown={event => event.stopPropagation()}
    >
      <header className="node-logs-popover-header">
        <span className="node-logs-popover-title">
          {title || nodeId}
        </span>
        <span className="node-logs-popover-count">
          {t('canvas.nodeLogs.count', {
            count: nodeLogs.length,
            defaultValue: '{{count}} lines',
          })}
        </span>
        <button
          type="button"
          className="btn btn-icon btn-sm"
          onClick={onClose}
          aria-label={t('common.close', { defaultValue: 'Close' })}
          title={t('common.close', { defaultValue: 'Close' })}
        >
          <Icon name="close" size={12} />
        </button>
      </header>

      <div className="node-logs-popover-body" ref={bodyRef}>
        {nodeLogs.length === 0 ? (
          <p className="node-logs-popover-empty">
            {t('canvas.nodeLogs.empty', {
              defaultValue: 'No logs for this node yet. Run the workflow to produce output.',
            })}
          </p>
        ) : (
          nodeLogs.map((entry, index) => (
            <div
              key={`${entry.timestamp}-${index}`}
              className={`node-logs-popover-line is-${entry.level}`}
            >
              <span className="node-logs-popover-time">
                {entry.timestamp.slice(11, 19)}
              </span>
              <span className="node-logs-popover-message">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
