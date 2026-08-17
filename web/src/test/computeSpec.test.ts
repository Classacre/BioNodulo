import { describe, it, expect } from 'vitest';
import {
  QUICK_SIZES,
  customComputeRate,
  specCreditsPerHour,
  specLabel,
  capsForPlanName,
  computeCapsForPlan,
  sizeAllowed,
  specToRunBody,
} from '../utils/computeSpec';

describe('customComputeRate (mirror of server sell-rates)', () => {
  it('8 vCPU / 64 GB is RAM-bound', () => {
    // Repriced 2026-08-01: 64 * 0.000195 = 0.01248 now exceeds 8 * 0.00127,
    // so this shape flipped from vCPU-bound to RAM-bound.
    expect(customComputeRate(8, 64)).toBeCloseTo(0.01248, 6);
  });
  it('4 vCPU / 128 GB is RAM-bound', () => {
    expect(customComputeRate(4, 128)).toBeCloseTo(0.02496, 7);
  });
});

describe('specCreditsPerHour / specLabel', () => {
  it('custom hourly cost + label', () => {
    // 12 vCPU / 96 GB → max(12*0.00101, 96*0.0000787)=0.01212 → 44 cr/hr
    expect(specCreditsPerHour({ kind: 'custom', vcpu: 12, ramGb: 96 })).toBe(67);
    expect(specLabel({ kind: 'custom', vcpu: 12, ramGb: 96 })).toBe('12 vCPU / 96 GB');
  });
  it('legacy profile maps to a size + labels by dims', () => {
    expect(specLabel({ kind: 'profile', profile: 'medium' })).toBe('8 vCPU / 64 GB');
  });
});

describe('capsForPlanName (§33 preset-free)', () => {
  it('free allows custom but caps at 4 vCPU / 16 GB', () => {
    const caps = capsForPlanName('free');
    expect(caps.allowsCustom).toBe(true);
    expect(caps.maxVcpu).toBe(4);
    expect(caps.maxRamGb).toBe(16);
  });
  it('paid plans are unlimited', () => {
    const caps = capsForPlanName('professional');
    expect(caps.allowsCustom).toBe(true);
    expect(caps.maxRamGb).toBeGreaterThanOrEqual(4096);
  });
  it('null plan treated as free (still allows custom, capped)', () => {
    expect(capsForPlanName(null).allowsCustom).toBe(true);
    expect(capsForPlanName(null).maxVcpu).toBe(4);
  });
});

describe('sizeAllowed', () => {
  it('gates a quick size against the plan cap', () => {
    const free = capsForPlanName('free');
    expect(sizeAllowed(free, 2, 16)).toBe(true);
    expect(sizeAllowed(free, 8, 64)).toBe(false);
    expect(sizeAllowed(capsForPlanName('professional'), 32, 256)).toBe(true);
  });
});

describe('computeCapsForPlan unlimited (paid)', () => {
  it('treats 0 RAM as a high cap', () => {
    expect(computeCapsForPlan('enterprise', 0).maxRamGb).toBeGreaterThanOrEqual(4096);
  });
});

describe('QUICK_SIZES + specToRunBody', () => {
  it('quick sizes cover XS..XXL with the GPU (T4) preset between L and XL', () => {
    expect(QUICK_SIZES.map(q => q.label)).toEqual(['XS', 'S', 'M', 'L', 'GPU (T4)', 'XL', 'XXL']);
    const gpu = QUICK_SIZES.find(q => q.profile === 'gpu');
    expect(gpu).toMatchObject({ vcpu: 4, ramGb: 16, profile: 'gpu' });
  });
  it('serializes CPU sizes to a custom compute body', () => {
    expect(specToRunBody({ kind: 'custom', vcpu: 8, ramGb: 64 })).toEqual({ compute: { vcpu: 8, ramGb: 64 } });
    expect(specToRunBody({ kind: 'profile', profile: 'large' })).toEqual({ compute: { vcpu: 16, ramGb: 128 } });
  });
  it('serializes the GPU preset as a named resourceProfile', () => {
    // An accelerator cannot be expressed as {vcpu, ramGb}; the GPU preset must
    // submit by name so the server provisions (and bills) the T4.
    expect(specToRunBody({ kind: 'profile', profile: 'gpu' })).toEqual({ resourceProfile: 'gpu' });
  });
});

describe('GPU preset (mirror of the server gpu profile)', () => {
  it('is accelerator-priced, not CPU/RAM-formula priced', () => {
    // 0.01061 credits/s -> 38 credits/hr; the 4/16 formula would quote 18.
    expect(specCreditsPerHour({ kind: 'profile', profile: 'gpu' })).toBe(38);
  });
  it('labels with its T4, while legacy CPU profiles label by dims', () => {
    expect(specLabel({ kind: 'profile', profile: 'gpu' })).toBe('4 vCPU / 16 GB · T4 GPU');
    expect(specLabel({ kind: 'profile', profile: 'medium' })).toBe('8 vCPU / 64 GB');
  });
});
