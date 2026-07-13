import { useMemo } from 'react';
import { useAtom, useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { cloudConfigAtom, computeSpecAtom } from '../../state/appAtoms';
import {
  QUICK_SIZES,
  capsForPlanName,
  specCreditsPerHour,
  specLabel,
  specDims,
  customComputeRate,
  sizeAllowed,
  MIN_GB_PER_VCPU,
} from '../../utils/computeSpec';

interface ComputePanelProps {
  onClose: () => void;
}

const VCPU_STEPS = [1, 2, 4, 8, 12, 16, 24, 32, 48, 64];

/**
 * Cloud compute selector embedded in the editor's left rail (signed-in only).
 * Users choose ANY CPU/RAM with the sliders (or a quick-size shortcut); Free is
 * capped at 4 vCPU / 16 GB, paid plans are unlimited. Priced live by the same
 * formula the server bills at (utils/computeSpec — mirror of the website's
 * resource-profiles). The selection persists to computeSpecAtom and is sent with
 * the next run as a custom { vcpu, ramGb } spec.
 */
export default function ComputePanel({ onClose }: ComputePanelProps) {
  const { t } = useTranslation();
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const [spec, setSpec] = useAtom(computeSpecAtom);
  const plan = cloudConfig?.plan ?? null;
  const accountUrl = cloudConfig?.accountUrl ?? null;

  const caps = useMemo(() => capsForPlanName(plan), [plan]);
  const creditsPerHour = specCreditsPerHour(spec);
  const current = specDims(spec);

  const vcpuChoices = VCPU_STEPS.filter(v => v <= caps.maxVcpu);
  const upgradeUrl = accountUrl ? `${accountUrl.replace(/\/+$/, '')}/pricing` : null;
  const isFree = !plan || plan === 'free';

  const setCustom = (vcpu: number, ramGb: number) => {
    const clampedVcpu = Math.min(caps.maxVcpu, Math.max(1, vcpu));
    const clampedRam = Math.min(
      caps.maxRamGb,
      Math.max(clampedVcpu * MIN_GB_PER_VCPU, ramGb),
    );
    setSpec({ kind: 'custom', vcpu: clampedVcpu, ramGb: clampedRam });
  };

  const pickSize = (vcpu: number, ramGb: number) => setCustom(vcpu, ramGb);
  const isActiveSize = (vcpu: number, ramGb: number) =>
    current.vcpu === vcpu && current.ramGb === ramGb;

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>{t('compute.title', { defaultValue: 'Cloud compute' })}</span>
        <button className="btn btn-icon" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}>
          <Icon name="close" size={14} />
        </button>
      </div>

      <div className="rail-panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16 }}>
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

        {/* Quick-size shortcuts (each just sets a custom spec) */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{t('compute.quickSizes', { defaultValue: 'Quick sizes' })}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {QUICK_SIZES.map(q => {
              const allowed = sizeAllowed(caps, q.vcpu, q.ramGb);
              return (
                <button
                  key={q.label}
                  className={`btn btn-sm ${isActiveSize(q.vcpu, q.ramGb) ? 'btn-primary' : ''}`}
                  disabled={!allowed}
                  title={allowed
                    ? `${q.vcpu} vCPU / ${q.ramGb} GB · ${Math.round(customComputeRate(q.vcpu, q.ramGb) * 3600)} cr/hr`
                    : t('compute.lockedSize', { defaultValue: 'Upgrade your plan to use this size' })}
                  onClick={() => pickSize(q.vcpu, q.ramGb)}
                >
                  {q.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom sliders — available to everyone (Free capped at 4 vCPU / 16 GB) */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
            {t('compute.custom', { defaultValue: 'Choose CPU & RAM' })}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              <span style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{t('compute.vcpu', { defaultValue: 'vCPU' })}</span>
                <strong>{current.vcpu}</strong>
              </span>
              <input
                type="range" min={0} max={Math.max(0, vcpuChoices.length - 1)} step={1}
                value={Math.max(0, vcpuChoices.indexOf(current.vcpu))}
                onChange={e => {
                  const vcpu = vcpuChoices[Number(e.target.value)] ?? vcpuChoices[0];
                  setCustom(vcpu, current.ramGb);
                }}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              <span style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{t('compute.ram', { defaultValue: 'RAM (GB)' })}</span>
                <strong>{current.ramGb}</strong>
              </span>
              <input
                type="range"
                min={current.vcpu * MIN_GB_PER_VCPU}
                max={caps.maxRamGb}
                step={4}
                value={current.ramGb}
                onChange={e => setCustom(current.vcpu, Number(e.target.value))}
              />
            </label>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              ≈ {Math.round(customComputeRate(current.vcpu, current.ramGb) * 3600).toLocaleString()} {t('compute.creditsPerHour', { defaultValue: 'credits / hr' })}
            </div>
          </div>

          {isFree && (
            <div style={{
              marginTop: 12,
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
    </div>
  );
}
