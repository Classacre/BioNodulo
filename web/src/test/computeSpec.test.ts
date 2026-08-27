import { describe, it, expect } from 'vitest';
import {
  customComputeRate,
  gpuComputeRate,
  specCreditsPerHour,
  specLabel,
  specDims,
  specGpuCount,
  isGpuSpec,
  clampGpuSpec,
  capsForPlanName,
  computeCapsForPlan,
  sizeAllowed,
  specToRunBody,
  recommendComputeSpec,
  specFromRecommendation,
  GPU_A10_CREDIT_PER_SECOND,
  GPU_BASE_RAM_GB,
  GPU_BASE_VCPU,
  GPU_MAX_COUNT,
  GPU_MIN_VCPU,
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
    // 12 vCPU / 96 GB → max(12*0.00127, 96*0.000195)=0.01872 → 67 cr/hr
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
  it('gates a size against the plan cap', () => {
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

describe('specToRunBody (sliders-only spec)', () => {
  it('serializes CPU sizes to a custom compute body', () => {
    expect(specToRunBody({ kind: 'custom', vcpu: 8, ramGb: 64 })).toEqual({ compute: { vcpu: 8, ramGb: 64 } });
    expect(specToRunBody({ kind: 'profile', profile: 'large' })).toEqual({ compute: { vcpu: 16, ramGb: 128 } });
  });
  it('serializes the GPU preset as a named resourceProfile', () => {
    // An accelerator cannot be expressed as {vcpu,ramGb}; the GPU worker must
    // submit by name so the server provisions (and bills) the A10.
    expect(specToRunBody({ kind: 'profile', profile: 'gpu' })).toEqual({ resourceProfile: 'gpu' });
  });
  it('serializes a CUSTOM GPU size as resourceProfile + customVcpu/customMemoryGb', () => {
    expect(specToRunBody({ kind: 'gpu', vcpu: 12, ramGb: 64 })).toEqual({
      resourceProfile: 'gpu',
      customVcpu: 12,
      customMemoryGb: 64,
    });
  });
  it('emits gpuCount only above the 1-GPU base', () => {
    expect(specToRunBody({ kind: 'gpu', vcpu: 8, ramGb: 32, gpuCount: 1 })).toEqual({
      resourceProfile: 'gpu',
      customVcpu: 8,
      customMemoryGb: 32,
    });
    expect(specToRunBody({ kind: 'gpu', vcpu: 8, ramGb: 32, gpuCount: 3 })).toEqual({
      resourceProfile: 'gpu',
      customVcpu: 8,
      customMemoryGb: 32,
      gpuCount: 3,
    });
    expect(specToRunBody({ kind: 'gpu', vcpu: GPU_BASE_VCPU, ramGb: GPU_BASE_RAM_GB, gpuCount: 2 })).toEqual({
      resourceProfile: 'gpu',
      gpuCount: 2,
    });
  });
  it('serializes the GPU base dims without overrides (base = preset)', () => {
    expect(specToRunBody({ kind: 'gpu', vcpu: GPU_BASE_VCPU, ramGb: GPU_BASE_RAM_GB }))
      .toEqual({ resourceProfile: 'gpu' });
  });
  it('clamps an out-of-bounds GPU selection into the serialize bounds', () => {
    // 2/8 clamps up to the 4/16 base — which serializes as the plain preset.
    expect(specToRunBody({ kind: 'gpu', vcpu: 2, ramGb: 8 })).toEqual({
      resourceProfile: 'gpu',
    });
    // Above-bounds values clamp to the 64/256 ceiling and DO carry overrides.
    expect(specToRunBody({ kind: 'gpu', vcpu: 999, ramGb: 999 })).toEqual({
      resourceProfile: 'gpu',
      customVcpu: 64,
      customMemoryGb: 256,
    });
  });
});

describe('GPU worker (customizable A10 base + count)', () => {
  it('is accelerator-priced: A10 base + the CPU/RAM formula', () => {
    // 4/16: 0.025 (A10) + max(4*0.00127, 16*0.000195)=0.00508 -> 108 cr/hr.
    expect(gpuComputeRate(4, 16)).toBeCloseTo(0.03008, 6);
    expect(specCreditsPerHour({ kind: 'gpu', vcpu: 4, ramGb: 16 })).toBe(108);
  });
  it('prices custom GPU dims and the multi-GPU tier', () => {
    // 16 vCPU / 64 GB: 0.025 + max(16*0.00127, 64*0.000195)=0.02032
    expect(gpuComputeRate(16, 64)).toBeCloseTo(0.04532, 6);
    // 2 GPUs: 2 * A10 + the same CPU/RAM portion
    expect(gpuComputeRate(16, 64, 2)).toBeCloseTo(0.025 * 2 + 0.02032, 6);
    expect(specCreditsPerHour({ kind: 'gpu', vcpu: 16, ramGb: 64, gpuCount: 2 }))
      .toBe(Math.round((0.025 * 2 + 0.02032) * 3600));
  });
  it('prices the legacy gpu preset with the same formula', () => {
    expect(specCreditsPerHour({ kind: 'profile', profile: 'gpu' }))
      .toBe(Math.round((GPU_A10_CREDIT_PER_SECOND + customComputeRate(4, 16)) * 3600));
  });
  it('labels the GPU as A10 (auto-matched), with ×N for multi-GPU', () => {
    expect(specLabel({ kind: 'profile', profile: 'gpu' })).toBe('4 vCPU / 16 GB · A10 (auto-matched)');
    expect(specLabel({ kind: 'gpu', vcpu: 16, ramGb: 64 })).toBe('16 vCPU / 64 GB · A10 (auto-matched)');
    expect(specLabel({ kind: 'gpu', vcpu: 16, ramGb: 64, gpuCount: 4 })).toBe('16 vCPU / 64 GB · A10 ×4 (auto-matched)');
  });
  it('isGpuSpec recognises both gpu kinds; dims come from the selection', () => {
    expect(isGpuSpec({ kind: 'gpu', vcpu: 8, ramGb: 32 })).toBe(true);
    expect(isGpuSpec({ kind: 'profile', profile: 'gpu' })).toBe(true);
    expect(isGpuSpec({ kind: 'custom', vcpu: 8, ramGb: 32 })).toBe(false);
    expect(specDims({ kind: 'gpu', vcpu: 12, ramGb: 32 })).toEqual({ vcpu: 12, ramGb: 32 });
    expect(specDims({ kind: 'profile', profile: 'gpu' })).toEqual({ vcpu: GPU_BASE_VCPU, ramGb: GPU_BASE_RAM_GB });
  });
  it('specGpuCount: 0 for CPU specs, clamped count for GPU specs', () => {
    expect(specGpuCount({ kind: 'custom', vcpu: 8, ramGb: 32 })).toBe(0);
    expect(specGpuCount({ kind: 'gpu', vcpu: 8, ramGb: 32 })).toBe(1);
    expect(specGpuCount({ kind: 'gpu', vcpu: 8, ramGb: 32, gpuCount: 2 })).toBe(2);
    expect(specGpuCount({ kind: 'gpu', vcpu: 8, ramGb: 32, gpuCount: 99 })).toBe(GPU_MAX_COUNT);
  });
  it('clamps GPU selections into the 4-64 vCPU / 16-256 GB / 1-4 GPU bounds', () => {
    expect(clampGpuSpec(2, 8)).toEqual({ vcpu: 4, ramGb: 16, gpuCount: 1 });
    expect(clampGpuSpec(999, 999, 9)).toEqual({ vcpu: 64, ramGb: 256, gpuCount: 4 });
    expect(GPU_MIN_VCPU).toBe(4);
  });
});

describe('recommendComputeSpec (workflow auto-sizing)', () => {
  const edges = (pairs: Array<[string, string]>) =>
    pairs.map(([from, to]) => ({ from: { node: from }, to: { node: to } }));

  it('empty workflow recommends a small CPU size', () => {
    const rec = recommendComputeSpec([], [], {});
    expect(rec.gpuCount).toBe(0);
    expect(rec.vcpu).toBe(2);
  });

  it('sizes vCPU to the busiest concurrent stage, not the node count', () => {
    // Chain of 3 nodes × 8 threads: stages are sequential → peak 8.
    const nodes = [
      { id: 'a', type: 'align', params: { threads: 8 } },
      { id: 'b', type: 'sort', params: { threads: 8 } },
      { id: 'c', type: 'call', params: { threads: 8 } },
    ];
    const rec = recommendComputeSpec(nodes, edges([['a', 'b'], ['b', 'c']]), {});
    expect(rec.vcpu).toBe(8);
    expect(rec.ramGb).toBe(32);
    expect(rec.gpuCount).toBe(0);
  });

  it('sums parallel branches: 3 × 4-thread forks at one stage → 12 vCPU', () => {
    const nodes = [
      { id: 'in', type: 'input' },
      { id: 'x', type: 'align', params: { threads: 4 } },
      { id: 'y', type: 'align', params: { threads: 4 } },
      { id: 'z', type: 'align', params: { threads: 4 } },
    ];
    const rec = recommendComputeSpec(nodes, edges([['in', 'x'], ['in', 'y'], ['in', 'z']]), {});
    expect(rec.vcpu).toBe(12);
  });

  it('falls back to registry thread defaults when params are unset', () => {
    const objectInfo = {
      align: { input_types: { required: { threads: { default: 6 } } } },
    };
    const rec = recommendComputeSpec([{ id: 'a', type: 'align' }], [], objectInfo);
    expect(rec.vcpu).toBe(6);
  });

  it('routes to the A10 worker when any node requires a GPU', () => {
    const objectInfo = { fold: { requires_gpu: true } };
    const rec = recommendComputeSpec(
      [{ id: 'f', type: 'fold' }],
      [],
      objectInfo,
    );
    expect(rec.gpuCount).toBe(1);
    expect(rec.vcpu).toBeGreaterThanOrEqual(4);
    expect(rec.ramGb).toBeGreaterThanOrEqual(16);
  });

  it('respects cycles without hanging', () => {
    const nodes = [
      { id: 'a', type: 'x', params: { threads: 4 } },
      { id: 'b', type: 'y', params: { threads: 4 } },
    ];
    const rec = recommendComputeSpec(nodes, edges([['a', 'b'], ['b', 'a']]), {});
    expect(rec.vcpu).toBeGreaterThan(0);
  });
});

describe('specFromRecommendation', () => {
  it('clamps a CPU recommendation into the free-plan caps', () => {
    const spec = specFromRecommendation(
      { vcpu: 32, ramGb: 128, gpuCount: 0, basis: 'x' },
      capsForPlanName('free'),
    );
    expect(spec).toEqual({ kind: 'custom', vcpu: 4, ramGb: 16 });
  });
  it('maps a GPU recommendation onto the gpu kind with bounds', () => {
    const spec = specFromRecommendation(
      { vcpu: 8, ramGb: 32, gpuCount: 1, basis: 'x' },
      capsForPlanName('professional'),
    );
    expect(spec).toEqual({ kind: 'gpu', vcpu: 8, ramGb: 32, gpuCount: 1 });
  });
});
