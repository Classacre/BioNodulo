import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import type { GraphNode } from '../canvas/WorkflowCanvas';
import { nodeCategoryDisplayLabel } from '../../utils/nodeCategories';
import { getVisibleInputSpecs } from '../../utils/nodeInputVisibility';
import { resolveNodeOutputs } from '../../utils/nodeOutputs';

interface NodeInfoPanelProps {
  node?: GraphNode;
  onClose: () => void;
}

export default function NodeInfoPanel({ node, onClose }: NodeInfoPanelProps) {
  const { t } = useTranslation();
  if (!node) return null;
  const meta = node.meta;
  const { required, optional } = getVisibleInputSpecs(meta, node.params);
  const outputs = resolveNodeOutputs(meta, node.params);
  const categoryLabel = nodeCategoryDisplayLabel(meta?.category, t, t('nodeLibrary.otherCategory'));
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
              {categoryLabel} · {meta.id}
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
          <InfoSection title={t('nodeDetails.requiredInputs')}>
            {Object.entries(required).map(([key, spec]) => (
              <ParamRow key={key} name={key} spec={spec as any} t={t} />
            ))}
          </InfoSection>
        )}

        {Object.keys(optional).length > 0 && (
          <InfoSection title={t('nodeDetails.optionalInputs')}>
            {Object.entries(optional).map(([key, spec]) => (
              <ParamRow key={key} name={key} spec={spec as any} t={t} />
            ))}
          </InfoSection>
        )}

        {/* Outputs */}
        {outputs.length > 0 && (
          <InfoSection title={t('nodeDetails.outputs')}>
            {outputs.map(output => (
              <div key={output.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text)' }}>{output.name}</span>
                <span style={{ color: 'var(--muted)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>{output.type}</span>
              </div>
            ))}
          </InfoSection>
        )}

        {/* Metadata */}
        <InfoSection title={t('nodeDetails.metadata')}>
          {meta?.version && <MetaRow label={t('nodeDetails.version')} value={meta.version} />}
          {meta?.requires_external_tools && meta.requires_external_tools.length > 0 && (
            <MetaRow
              label={t('nodeDetails.requires')}
              value={meta.requires_external_tools.join(', ')}
            />
          )}
          {meta?.environment && <MetaRow label={t('nodeDetails.environment')} value={meta.environment} />}
          {meta?.search_aliases && meta.search_aliases.length > 0 && (
            <MetaRow label={t('nodeDetails.aliases')} value={meta.search_aliases.join(', ')} />
          )}
          {meta?.citation_dois && meta.citation_dois.length > 0 && (
            <MetaRow label={t('nodeDetails.doi')} value={meta.citation_dois.join(', ')} />
          )}
          {meta?.citation_text && (
            <MetaRow label={t('nodeDetails.citation')} value={meta.citation_text} />
          )}
          {meta?.citation_urls && meta.citation_urls.length > 0 && (
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {meta.citation_urls.map(url => (
                <a key={url} href={url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent)', overflowWrap: 'anywhere' }}>
                  {url}
                </a>
              ))}
            </div>
          )}
          {meta?.documentation_url && (
            <div style={{ marginTop: 6 }}>
              <a href={meta.documentation_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent)' }}>
                {t('nodeDetails.openDocumentationLink')}
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
    <div style={{ display: 'grid', gridTemplateColumns: '80px minmax(0, 1fr)', gap: 8, padding: '3px 0', fontSize: 11 }}>
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <span style={{ color: 'var(--text)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, overflowWrap: 'anywhere', minWidth: 0 }}>{value}</span>
    </div>
  );
}

function ParamRow({ name, spec, t }: { name: string; spec: {
  type: string; default?: unknown; options?: string[]; min?: number; max?: number;
  tooltip?: string; label?: string; multiline?: boolean; accept?: string;
}; t: (key: string) => string }) {
  const label = spec.label || name;
  const defaultVal = spec.default !== undefined ? String(spec.default) : t('nodeDetails.noDefaultValue');
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
        <span>{t('nodeDetails.defaultLabel')}: <code style={{ background: 'var(--surface-2)', padding: '1px 4px', borderRadius: 3 }}>{defaultVal}</code></span>
        {options && <span>{t('nodeDetails.optionsLabel')}: {options}</span>}
        {spec.min !== undefined && <span>{t('nodeDetails.minLabel')}: {spec.min}</span>}
        {spec.max !== undefined && <span>{t('nodeDetails.maxLabel')}: {spec.max}</span>}
      </div>
    </div>
  );
}
