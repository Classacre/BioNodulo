// Client-side mirror of the cloud compute pricing model (kept in lockstep with
// bionodulo-website apps/web/lib/resource-profiles.ts). Used by the editor's
// Compute panel to show quick-size shortcuts, slider bounds, and a live
// credit/hr quote without a round-trip. The server re-validates + re-prices on
// submit, so this is purely for UX — never trusted for billing.

export type ResourceProfile =
  | 'micro' | 'small' | 'medium' | 'large' | 'gpu' | 'xlarge' | 'extreme';

// Published customer sell-rates (credits/second). 1 credit = $0.01. Mirror of
// the server's VCPU_CREDIT_RATE / RAM_GB_CREDIT_RATE.
// Repriced 2026-08-01. Mirror of the server's rates in
// bionodulo-website apps/web/lib/resource-profiles.ts -- the server re-prices on
// submit, so these exist only to quote the same number in the Compute panel.
export const VCPU_CREDIT_RATE = 0.00127;
export const RAM_GB_CREDIT_RATE = 0.000195;
export const MIN_GB_PER_VCPU = 4;

/**
 * Per-A10-GPU sell-rate (credits/second), mirror of the server's
 * GPU_A10_CREDIT_PER_SECOND. The GPU base is priced from OCI's A10 (its
 * primary accelerator), not the old AWS T4 pin; the user's chosen vCPU/RAM is
 * billed on top via the regular formula.
 */
export const GPU_A10_CREDIT_PER_SECOND = 0.025;

/** GPU worker sizing bounds + memory quick options (mirror of the server). */
export const GPU_MIN_VCPU = 4;
export const GPU_MAX_VCPU = 64;
export const GPU_MIN_RAM_GB = 16;
export const GPU_MAX_RAM_GB = 256;
export const GPU_MEMORY_OPTIONS = [16, 32, 64, 128] as const;
export const GPU_BASE_VCPU = 4;
export const GPU_BASE_RAM_GB = 16;

/** Credits/second for a GPU worker: A10 base + the CPU/RAM formula. */
export function gpuComputeRate(vcpu: number, ramGb: number, gpuCount = 1): number {
  const gpus = Math.max(1, Math.min(4, Math.round(gpuCount)));
  return gpus * GPU_A10_CREDIT_PER_SECOND + customComputeRate(vcpu, ramGb);
}

/** Credits/second for an arbitrary spec (max of CPU- and RAM-derived). */
export function customComputeRate(vcpu: number, ramGb: number): number {
  return Math.max(
    Math.max(0, vcpu) * VCPU_CREDIT_RATE,
    Math.max(0, ramGb) * RAM_GB_CREDIT_RATE,
  );
}

export interface QuickSize {
  label: string;
  vcpu: number;
  ramGb: number;
  /**
   * When set, this shortcut selects the named preset instead of a custom
   * {vcpu, ramGb}. Only the GPU preset works this way — the accelerator
   * cannot be expressed as CPU/RAM, so it is submitted as
   * `resourceProfile: 'gpu'` (+ customVcpu/customMemoryGb when resized).
   */
  profile?: 'gpu';
}

/**
 * Convenience "quick pick" sizes — NOT locked tiers. Each just sets a custom
 * {vcpu, ramGb}; users can also freely slide to anything within their plan cap.
 * The GPU (A10) shortcut is the exception: it submits the named `gpu` preset,
 * whose vCPU/RAM the user can then adjust in the GPU sizing controls.
 */
export const QUICK_SIZES: QuickSize[] = [
  { label: 'XS', vcpu: 2, ramGb: 16 },
  { label: 'S', vcpu: 4, ramGb: 16 },
  { label: 'M', vcpu: 8, ramGb: 64 },
  { label: 'L', vcpu: 16, ramGb: 128 },
  { label: 'GPU (A10)', vcpu: 4, ramGb: 16, profile: 'gpu' },
  { label: 'XL', vcpu: 32, ramGb: 256 },
  { label: 'XXL', vcpu: 64, ramGb: 512 },
];

/**
 * A run's compute size. The editor emits a custom {vcpu, ramGb} for CPU sizes
 * and a GPU spec (dims + the named preset) for GPU workers; the `profile`
 * variant is retained only for backward-compat deserialization.
 */
export type ComputeSpec =
  | { kind: 'profile'; profile: ResourceProfile }
  | { kind: 'gpu'; vcpu: number; ramGb: number }
  | { kind: 'custom'; vcpu: number; ramGb: number };

/** True when the spec runs on the GPU worker (A10, auto-matched instance). */
export function isGpuSpec(spec: ComputeSpec): boolean {
  return spec.kind === 'gpu' || (spec.kind === 'profile' && spec.profile === 'gpu');
}

/** Coerce any spec into concrete vCPU/RAM (legacy profiles map to a size). */
export function specDims(spec: ComputeSpec): { vcpu: number; ramGb: number } {
  if (spec.kind === 'custom' || spec.kind === 'gpu') {
    return { vcpu: spec.vcpu, ramGb: spec.ramGb };
  }
  const map: Record<ResourceProfile, { vcpu: number; ramGb: number }> = {
    micro: { vcpu: 1, ramGb: 4 },
    small: { vcpu: 2, ramGb: 16 },
    medium: { vcpu: 8, ramGb: 64 },
    large: { vcpu: 16, ramGb: 128 },
    gpu: { vcpu: GPU_BASE_VCPU, ramGb: GPU_BASE_RAM_GB },
    xlarge: { vcpu: 32, ramGb: 256 },
    extreme: { vcpu: 64, ramGb: 512 },
  };
  return map[spec.profile] ?? { vcpu: 2, ramGb: 16 };
}

/** Clamp a GPU selection into the server's GPU bounds. */
export function clampGpuSpec(vcpu: number, ramGb: number): { vcpu: number; ramGb: number } {
  return {
    vcpu: Math.min(GPU_MAX_VCPU, Math.max(GPU_MIN_VCPU, Math.round(vcpu))),
    ramGb: Math.min(GPU_MAX_RAM_GB, Math.max(GPU_MIN_RAM_GB, Math.round(ramGb))),
  };
}

export function specCreditPerSecond(spec: ComputeSpec): number {
  // GPU workers are priced by accelerator + the CPU/RAM formula.
  if (isGpuSpec(spec)) {
    const { vcpu, ramGb } = specDims(spec);
    return gpuComputeRate(vcpu, ramGb);
  }
  const dims = specDims(spec);
  return customComputeRate(dims.vcpu, dims.ramGb);
}

export function specCreditsPerHour(spec: ComputeSpec): number {
  return Math.round(specCreditPerSecond(spec) * 3600);
}

export function specLabel(spec: ComputeSpec): string {
  if (isGpuSpec(spec)) {
    const { vcpu, ramGb } = specDims(spec);
    return `${vcpu} vCPU / ${ramGb} GB · OCI A10 (auto-matched)`;
  }
  const { vcpu, ramGb } = specDims(spec);
  return `${vcpu} vCPU / ${ramGb} GB`;
}

export interface ComputeCaps {
  maxRamGb: number;
  maxVcpu: number;
  /** Free is capped; everyone can pick custom (no locked-preset tier anymore). */
  allowsCustom: boolean;
}

/**
 * Per-plan max RAM (GB), mirroring the server. 0 = unlimited (paid plans let the
 * user choose any size). Free is the only capped tier.
 */
export const PLAN_MAX_RAM_GB: Record<string, number> = {
  free: 16,
  starter: 0,
  professional: 0,
  team: 0,
  enterprise: 0,
};

/** Per-plan caps (mirror of the server computeCapsForPlan). */
export function computeCapsForPlan(plan: string | null, maxRamGb: number): ComputeCaps {
  if (!plan || plan === 'free') {
    return { maxRamGb: 16, maxVcpu: 4, allowsCustom: true };
  }
  const cap = maxRamGb > 0 ? maxRamGb : 4096;
  return {
    maxRamGb: cap,
    maxVcpu: Math.max(1, Math.floor(cap / MIN_GB_PER_VCPU)),
    allowsCustom: true,
  };
}

/** Caps for a plan name, looking up its RAM limit from PLAN_MAX_RAM_GB. */
export function capsForPlanName(plan: string | null): ComputeCaps {
  return computeCapsForPlan(plan, PLAN_MAX_RAM_GB[plan ?? 'free'] ?? 16);
}

/** Whether a size is within a plan's caps. */
export function sizeAllowed(caps: ComputeCaps, vcpu: number, ramGb: number): boolean {
  return vcpu <= caps.maxVcpu && ramGb <= caps.maxRamGb;
}

/**
 * Serialize a ComputeSpec into the /api/runs request shape. CPU sizes go as a
 * custom {vcpu, ramGb}; the GPU preset goes as `resourceProfile: 'gpu'` (the
 * accelerator cannot be expressed as CPU/RAM), with customVcpu/customMemoryGb
 * riding along when the user resized the GPU worker. Legacy CPU profile specs
 * still map to their custom dims for backward compatibility.
 */
export function specToRunBody(spec: ComputeSpec): {
  resourceProfile?: string;
  compute?: { vcpu: number; ramGb: number };
  customVcpu?: number;
  customMemoryGb?: number;
} {
  if (spec.kind === 'gpu') {
    const { vcpu, ramGb } = clampGpuSpec(spec.vcpu, spec.ramGb);
    // The GPU BASE dims need no override; anything else sizes the worker.
    if (vcpu === GPU_BASE_VCPU && ramGb === GPU_BASE_RAM_GB) {
      return { resourceProfile: 'gpu' };
    }
    return { resourceProfile: 'gpu', customVcpu: vcpu, customMemoryGb: ramGb };
  }
  if (spec.kind === 'profile' && spec.profile === 'gpu') {
    return { resourceProfile: 'gpu' };
  }
  const { vcpu, ramGb } = specDims(spec);
  return { compute: { vcpu, ramGb } };
}
