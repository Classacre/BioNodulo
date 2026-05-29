import Icon from '../ui/Icon';
import type { GraphNode } from '../canvas/WorkflowCanvas';

interface NodeInfoPanelProps {
  node?: GraphNode;
  onClose: () => void;
}

export default function NodeInfoPanel({ node, onClose }: NodeInfoPanelProps) {
  if (!node) return null;
  const meta = node.meta;
  const required = meta?.input_types?.required || {};
  const optional = meta?.input_types?.optional || {};
  // const hidden = meta?.input_types?.hidden || {};

  return (
    <div className="node-editor" style={{ maxWidth: 380 }}>
      <div
        className="node-editor-header"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: node.color,
          color: 'white',
          borderRadius: '10px 10px 0 0',
          padding: '10px 14px',
        }}
      >
        <div>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{node.title}</div>
          {meta?.category && (
            <div style={{ fontSize: 10, opacity: 0.85, marginTop: 2 }}>
              {meta.category} · {meta.id}
            </div>
          )}
        </div>
        <button className="btn btn-icon btn-sm" onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'white' }}>
          <Icon name="close" size={14} />
        </button>
      </div>

      <div className="node-editor-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
        {meta?.description && (
          <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5, marginBottom: 12, padding: 10, borderRadius: 6, background: 'var(--surface-2)' }}>
            {meta.description}
          </div>
        )}

        {/* Inputs */}
        {Object.keys(required).length > 0 && (
          <InfoSection title="Required Inputs">
            {Object.entries(required).map(([key, spec]) => (
              <ParamRow key={key} name={key} spec={spec as any} />
            ))}
          </InfoSection>
        )}

        {Object.keys(optional).length > 0 && (
          <InfoSection title="Optional Inputs">
            {Object.entries(optional).map(([key, spec]) => (
              <ParamRow key={key} name={key} spec={spec as any} />
            ))}
          </InfoSection>
        )}

        {/* Outputs */}
        {meta?.return_types && meta.return_types.length > 0 && (
          <InfoSection title="Outputs">
            {meta.return_types.map((t, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text)' }}>{meta.return_names?.[i] || t}</span>
                <span style={{ color: 'var(--muted)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>{t}</span>
              </div>
            ))}
          </InfoSection>
        )}

        {/* Metadata */}
        <InfoSection title="Metadata">
          {meta?.version && <MetaRow label="Version" value={meta.version} />}
          {meta?.requires_external_tools && meta.requires_external_tools.length > 0 && (
            <MetaRow
              label="Requires"
              value={meta.requires_external_tools.join(', ')}
            />
          )}
          {meta?.environment && <MetaRow label="Environment" value={meta.environment} />}
          {meta?.search_aliases && meta.search_aliases.length > 0 && (
            <MetaRow label="Aliases" value={meta.search_aliases.join(', ')} />
          )}
          {meta?.documentation_url && (
            <div style={{ marginTop: 6 }}>
              <a href={meta.documentation_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent)' }}>
                Open Documentation ↗
              </a>
            </div>
          )}
        </InfoSection>
      </div>
    </div>
  );
}

function InfoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 6, letterSpacing: '0.05em' }}>
        {title}
      </div>
      <div style={{ background: 'var(--surface)', borderRadius: 6, padding: '6px 10px', border: '1px solid var(--border)' }}>
        {children}
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 11 }}>
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <span style={{ color: 'var(--text)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>{value}</span>
    </div>
  );
}

function ParamRow({ name, spec }: { name: string; spec: {
  type: string; default?: unknown; options?: string[]; min?: number; max?: number;
  tooltip?: string; label?: string; multiline?: boolean; accept?: string;
} }) {
  const label = spec.label || name;
  const defaultVal = spec.default !== undefined ? String(spec.default) : '—';
  const options = spec.options ? spec.options.join(', ') : '';

  return (
    <div style={{ padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, color: 'var(--text)' }}>{label}</span>
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: 'var(--muted)', background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 4 }}>
          {spec.type}
        </span>
      </div>
      {spec.tooltip && (
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{spec.tooltip}</div>
      )}
      <div style={{ display: 'flex', gap: 12, marginTop: 3, fontSize: 10, color: 'var(--muted)' }}>
        <span>Default: <code style={{ background: 'var(--surface-2)', padding: '1px 4px', borderRadius: 3 }}>{defaultVal}</code></span>
        {options && <span>Options: {options}</span>}
        {spec.min !== undefined && <span>Min: {spec.min}</span>}
        {spec.max !== undefined && <span>Max: {spec.max}</span>}
      </div>
    </div>
  );
}
