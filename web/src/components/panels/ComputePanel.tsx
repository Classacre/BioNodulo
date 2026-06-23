import { useMemo } from 'react';
import { useAtom, useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { cloudConfigAtom, computeSpecAtom } from '../../state/appAtoms';
import {
  PRESETS,
  capsForPlanName,
  specCreditsPerHour,
  specLabel,
  customComputeRate,
  MIN_GB_PER_VCPU,
  type ResourceProfile,
} from '../../utils/computeSpec';

interface ComputePanelProps {
  onClose: () => void;
}

const VCPU_STEPS = [1, 2, 4, 8, 12, 16, 24, 32, 48, 64];

/**
 * Cloud compute selector embedded in the editor's left rail (signed-in only).
 * Free plans pick from Micro/Small presets; paid plans unlock the larger presets
 * plus arbitrary CPU/RAM sliders, priced live by the same formula the server
 * bills at (see utils/computeSpec — mirror of the website's resource-profiles).
 * The selection persists to computeSpecAtom and is sent with the next run.
 */
export default function ComputePanel({ onClose }: ComputePanelProps) {
  const { t } = useTranslation();
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const [spec, setSpec] = useAtom(computeSpecAtom);
  const plan = cloudConfig?.plan ?? null;
  const accountUrl = cloudConfig?.accountUrl ?? null;

  const caps = useMemo(() => capsForPlanName(plan), [plan]);
  const creditsPerHour = specCreditsPerHour(spec);

  const custom = spec.kind === 'custom'
    ? spec
    : (() => {
        const p = PRESETS.find(x => x.profile === spec.profile) ?? PRESETS[1];
        return { kind: 'custom' as const, vcpu: p.vcpu, ramGb: p.ramGb };
      })();

  const vcpuChoices = VCPU_STEPS.filter(v => v <= caps.maxVcpu);
  const upgradeUrl = accountUrl ? `${accountUrl.replace(/\/+$/, '')}/pricing` : null;

  const setCustom = (vcpu: number, ramGb: number) => {
    const clampedRam = Math.min(caps.maxRamGb, Math.max(vcpu * MIN_GB_PER_VCPU, ramGb));
    setSpec({ kind: 'custom', vcpu, ramGb: clampedRam });
  };

  const pickPreset = (profile: ResourceProfile) => setSpec({ kind: 'profile', profile });

  const isActivePreset = (profile: ResourceProfile) =>
    spec.kind === 'profile' && spec.profile === profile;

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

        {/* Preset chips */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{t('compute.presets', { defaultValue: 'Presets' })}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {PRESETS.map(p => {
              const allowed = caps.allowedProfiles.includes(p.profile);
              return (
                <button
                  key={p.profile}
                  className={`btn btn-sm ${isActivePreset(p.profile) ? 'btn-primary' : ''}`}
                  disabled={!allowed}
                  title={allowed
                    ? `${p.vcpu} vCPU / ${p.ramGb} GB · ${Math.round(p.creditPerSecond * 3600)} cr/hr`
                    : t('compute.lockedPreset', { defaultValue: 'Upgrade your plan to use this size' })}
                  onClick={() => pickPreset(p.profile)}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom sliders (paid only) */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
            {t('compute.custom', { defaultValue: 'Custom' })}
          </div>
          {caps.allowsCustom ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                <span style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{t('compute.vcpu', { defaultValue: 'vCPU' })}</span>
                  <strong>{custom.vcpu}</strong>
                </span>
                <input
                  type="range" min={0} max={vcpuChoices.length - 1} step={1}
                  value={Math.max(0, vcpuChoices.indexOf(custom.vcpu))}
                  onChange={e => {
                    const vcpu = vcpuChoices[Number(e.target.value)] ?? vcpuChoices[0];
                    setCustom(vcpu, custom.ramGb);
                  }}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                <span style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{t('compute.ram', { defaultValue: 'RAM (GB)' })}</span>
                  <strong>{custom.ramGb}</strong>
                </span>
                <input
                  type="range"
                  min={custom.vcpu * MIN_GB_PER_VCPU}
                  max={caps.maxRamGb}
                  step={4}
                  value={custom.ramGb}
                  onChange={e => setCustom(custom.vcpu, Number(e.target.value))}
                />
              </label>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                {t('compute.estimate', {
                  defaultValue: `≈ ${Math.round(customComputeRate(custom.vcpu, custom.ramGb) * 3600).toLocaleString()} credits/hr`,
                  credits: Math.round(customComputeRate(custom.vcpu, custom.ramGb) * 3600).toLocaleString(),
                })}
              </div>
            </div>
          ) : (
            <div style={{
              border: '1px dashed var(--border, rgba(127,127,127,0.3))', borderRadius: 8, padding: 12,
              fontSize: 13, color: 'var(--muted)',
            }}>
              {t('compute.freeLocked', { defaultValue: 'Custom compute is a paid feature. Upgrade to choose any CPU/RAM.' })}
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
