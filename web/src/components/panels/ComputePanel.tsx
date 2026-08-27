import { useEffect, useMemo } from 'react';
import { useAtom, useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { cloudConfigAtom, computeAutoAtom, computeSpecAtom } from '../../state/appAtoms';
import {
  GPU_MAX_COUNT,
  capsForPlanName,
  clampGpuSpec,
  computeAutoNote,
  customComputeRate,
  gpuComputeRate,
  isGpuSpec,
  MIN_GB_PER_VCPU,
  recommendComputeSpec,
  specCreditsPerHour,
  specDims,
  specFromRecommendation,
  specGpuCount,
  specLabel,
  type ComputeSpec,
  type RecommenderEdge,
  type RecommenderNode,
} from '../../utils/computeSpec';
import type { NodeMetadata } from '../../types';

interface ComputePanelProps {
  onClose: () => void;
  /** Active workflow graph — drives the auto-size recommendation. */
  nodes: RecommenderNode[];
  edges: RecommenderEdge[];
  objectInfo: Record<string, NodeMetadata | undefined>;
}

/**
 * Cloud compute selector embedded in the editor's left rail (signed-in only).
 * Pure sliders — CPU, RAM, and GPU count (0 = CPU-only, 1-4 = A10 workers) —
 * no preset buttons: any combination maps onto a cloud shape via the dispatch
 * optimizer (OCI first, AWS fallback). While auto-size is on, the spec tracks
 * the workflow (threads demand per concurrent stage, GPU-requiring nodes) and
 * any manual edit turns auto off. Priced live by the same formula the server
 * bills at (utils/computeSpec — mirror of the website's resource-profiles).
 */
export default function ComputePanel({ onClose, nodes, edges, objectInfo }: ComputePanelProps) {
  const { t } = useTranslation();
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const [spec, setSpec] = useAtom(computeSpecAtom);
  const [auto, setAuto] = useAtom(computeAutoAtom);
  const plan = cloudConfig?.plan ?? null;
  const accountUrl = cloudConfig?.accountUrl ?? null;

  const caps = useMemo(() => capsForPlanName(plan), [plan]);
  const creditsPerHour = specCreditsPerHour(spec);
  const current = specDims(spec);
  const isGpu = isGpuSpec(spec);
  const gpuCount = specGpuCount(spec);

  const recommendation = useMemo(
    () => recommendComputeSpec(nodes, edges, objectInfo),
    [nodes, edges, objectInfo],
  );

  // Auto-size: follow the workflow until the user takes manual control.
  useEffect(() => {
    if (!auto) return;
    const next = specFromRecommendation(recommendation, caps);
    setSpec(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, recommendation, caps.maxVcpu, caps.maxRamGb]);

  const upgradeUrl = accountUrl ? `${accountUrl.replace(/\/+$/, '')}/pricing` : null;
  const isFree = !plan || plan === 'free';

  /** Any manual slider edit: apply the change and stop tracking the workflow. */
  const applyManual = (next: ComputeSpec) => {
    setAuto(false);
    setSpec(next);
  };

  const setCustom = (vcpu: number, ramGb: number) => {
    const clampedVcpu = Math.min(caps.maxVcpu, Math.max(1, vcpu));
    const clampedRam = Math.min(
      caps.maxRamGb,
      Math.max(clampedVcpu * MIN_GB_PER_VCPU, ramGb),
    );
    applyManual({ kind: 'custom', vcpu: clampedVcpu, ramGb: clampedRam });
  };

  const setGpu = (vcpu: number, ramGb: number, count: number) => {
    const gpuMaxVcpu = Math.min(64, caps.maxVcpu);
    const gpuMaxRam = Math.min(256, caps.maxRamGb);
    const clamped = clampGpuSpec(
      Math.min(gpuMaxVcpu, vcpu),
      Math.min(gpuMaxRam, ramGb),
      count,
    );
    applyManual({ kind: 'gpu', ...clamped });
  };

  /** GPU count drives the mode: 0 = CPU sliders, 1-4 = A10 worker sliders. */
  const setGpuCount = (count: number) => {
    if (count <= 0) {
      // Keep sensible CPU dims when dropping the GPU: same vCPU, RAM floored at
      // the CPU minimum ratio and the plan cap.
      setCustom(current.vcpu, current.ramGb);
      return;
    }
    setGpu(
      Math.max(4, current.vcpu),
      Math.max(16, current.ramGb),
      count,
    );
  };

  const sliderRow = (
    label: string,
    value: number,
    min: number,
    max: number,
    step: number,
    onChange: (v: number) => void,
    formatValue?: (v: number) => string,
  ) => (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
      <span style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>{label}</span>
        <strong>{formatValue ? formatValue(value) : value}</strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
      />
    </label>
  );

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>{t('compute.title', { defaultValue: 'Cloud compute' })}</span>
        <button className="btn btn-icon" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}>
          <Icon name="close" size={14} />
        </button>
      </div>

      <div className="rail-panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16 }}>
        {/* Auto-size: spec tracks the workflow until manually overridden */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
          border: '1px solid var(--border, rgba(127,127,127,0.25))', borderRadius: 8, padding: '8px 12px',
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600 }}>
              {t('compute.autoSize', { defaultValue: 'Auto-size for this workflow' })}
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={recommendation.basis}>
              {auto
                ? computeAutoNote(recommendation)
                : t('compute.autoOff', { defaultValue: 'Off — manual sliders in use' })}
            </div>
          </div>
          <button
            className={`btn btn-sm ${auto ? 'btn-primary' : ''}`}
            onClick={() => setAuto(!auto)}
            title={t('compute.autoTitle', { defaultValue: 'Match CPU/RAM/GPU to the workflow\u2019s thread and GPU demand' })}
          >
            {auto ? t('compute.autoOn', { defaultValue: 'Auto' }) : t('compute.autoEnable', { defaultValue: 'Use auto' })}
          </button>
        </div>

        {/* Current selection summary */}
        <div style={{
          border: '1px solid var(--border, rgba(127,127,127,0.25))', borderRadius: 8,
          padding: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{t('compute.selected', { defaultValue: 'Selected' })}</div>
            <div style={{ fontWeight: 600 }}>{specLabel(spec)}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 600 }}>{creditsPerHour.toLocaleString()}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{t('compute.creditsPerHour', { defaultValue: 'credits / hr' })}</div>
          </div>
        </div>

        {/* Sliders — GPU count first: 0 = CPU-only, 1-4 = A10 workers. */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {sliderRow(
            t('compute.gpuCount', { defaultValue: 'GPUs (A10)' }),
            gpuCount,
            0,
            GPU_MAX_COUNT,
            1,
            setGpuCount,
            v => (v === 0 ? t('compute.none', { defaultValue: 'None' }) : `×${v}`),
          )}

          {isGpu ? (
            <>
              {sliderRow(
                t('compute.vcpu', { defaultValue: 'vCPU' }),
                current.vcpu,
                4,
                Math.min(64, caps.maxVcpu),
                1,
                v => setGpu(v, current.ramGb, gpuCount),
              )}
              {sliderRow(
                t('compute.ram', { defaultValue: 'RAM (GB)' }),
                current.ramGb,
                Math.max(16, current.vcpu * MIN_GB_PER_VCPU),
                Math.min(256, caps.maxRamGb),
                4,
                v => setGpu(current.vcpu, v, gpuCount),
              )}
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                ≈ {Math.round(gpuComputeRate(current.vcpu, current.ramGb, gpuCount) * 3600).toLocaleString()} {t('compute.creditsPerHour', { defaultValue: 'credits / hr' })}
                {' · '}
                {t('compute.gpuAutoMatch', { defaultValue: 'cheapest matching GPU instance picked for you' })}
              </div>
            </>
          ) : (
            <>
              {sliderRow(
                t('compute.vcpu', { defaultValue: 'vCPU' }),
                current.vcpu,
                1,
                caps.maxVcpu,
                1,
                v => setCustom(v, current.ramGb),
              )}
              {sliderRow(
                t('compute.ram', { defaultValue: 'RAM (GB)' }),
                current.ramGb,
                current.vcpu * MIN_GB_PER_VCPU,
                caps.maxRamGb,
                4,
                v => setCustom(current.vcpu, v),
              )}
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                ≈ {Math.round(customComputeRate(current.vcpu, current.ramGb) * 3600).toLocaleString()} {t('compute.creditsPerHour', { defaultValue: 'credits / hr' })}
              </div>
            </>
          )}
        </div>

        {isFree && (
            <div style={{
              border: '1px dashed var(--border, rgba(127,127,127,0.3))', borderRadius: 8, padding: 12,
              fontSize: 13, color: 'var(--muted)',
            }}>
              {t('compute.freeCap', { defaultValue: 'Free plan is capped at 4 vCPU / 16 GB. Upgrade to choose any size.' })}
              {upgradeUrl && (
                <div style={{ marginTop: 8 }}>
                  <a className="btn btn-sm btn-primary" href={upgradeUrl} target="_blank" rel="noopener noreferrer">
                    {t('compute.upgrade', { defaultValue: 'Upgrade plan' })}
                  </a>
                </div>
              )}
            </div>
          )}
      </div>
    </div>
  );
}
