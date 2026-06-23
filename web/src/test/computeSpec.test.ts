import { describe, it, expect } from 'vitest';
import {
  PRESETS,
  customComputeRate,
  specCreditsPerHour,
  specLabel,
  capsForPlanName,
  computeCapsForPlan,
  specToRunBody,
} from '../utils/computeSpec';

describe('customComputeRate reproduces presets', () => {
  it.each(['small', 'medium', 'large', 'xlarge', 'extreme'] as const)('%s', (name) => {
    const p = PRESETS.find(x => x.profile === name)!;
    expect(customComputeRate(p.vcpu, p.ramGb)).toBeCloseTo(p.creditPerSecond, 6);
  });
});

describe('specCreditsPerHour / specLabel', () => {
  it('preset hourly cost', () => {
    expect(specCreditsPerHour({ kind: 'profile', profile: 'medium' })).toBe(1152);
    expect(specLabel({ kind: 'profile', profile: 'medium' })).toBe('Medium');
  });
  it('custom hourly cost + label', () => {
    expect(specCreditsPerHour({ kind: 'custom', vcpu: 12, ramGb: 96 })).toBe(1728);
    expect(specLabel({ kind: 'custom', vcpu: 12, ramGb: 96 })).toBe('12 vCPU / 96 GB');
  });
});

describe('capsForPlanName', () => {
  it('free locks to micro/small, no custom', () => {
    const caps = capsForPlanName('free');
    expect(caps.allowsCustom).toBe(false);
    expect(caps.allowedProfiles).toEqual(['micro', 'small']);
  });
  it('professional unlocks custom up to 128 GB', () => {
    const caps = capsForPlanName('professional');
    expect(caps.allowsCustom).toBe(true);
    expect(caps.maxRamGb).toBe(128);
    expect(caps.maxVcpu).toBe(32);
    expect(caps.allowedProfiles).not.toContain('xlarge');
  });
  it('null plan treated as free', () => {
    expect(capsForPlanName(null).allowsCustom).toBe(false);
  });
});

describe('computeCapsForPlan unlimited (enterprise)', () => {
  it('treats 0 RAM as 1024 cap', () => {
    expect(computeCapsForPlan('enterprise', 0).maxRamGb).toBe(1024);
  });
});

describe('specToRunBody', () => {
  it('preset -> resourceProfile', () => {
    expect(specToRunBody({ kind: 'profile', profile: 'large' })).toEqual({ resourceProfile: 'large' });
  });
  it('custom -> compute', () => {
    expect(specToRunBody({ kind: 'custom', vcpu: 8, ramGb: 64 })).toEqual({ compute: { vcpu: 8, ramGb: 64 } });
  });
});
