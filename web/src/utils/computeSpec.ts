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
 * The GPU preset's sell-rate (credits/second): one NVIDIA T4 on a g4dn.xlarge
 * (4 vCPU / 16 GB). The vCPU/RAM formula cannot price an accelerator, so the
 * server publishes this as a named profile rate — mirrored here for the same
 * quote-in-the-panel purpose.
 */
export const GPU_PROFILE_CREDIT_PER_SECOND = 0.01061;

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
   * {vcpu, ramGb}. Only the GPU preset works this way — an accelerator cannot
   * be expressed as CPU/RAM, so it is submitted as `resourceProfile: 'gpu'`.
   */
  profile?: 'gpu';
}

/**
 * Convenience "quick pick" sizes — NOT locked tiers. Each just sets a custom
 * {vcpu, ramGb}; users can also freely slide to anything within their plan cap.
 * The GPU (T4) shortcut is the exception: it submits the named `gpu` preset.
 */
export const QUICK_SIZES: QuickSize[] = [
  { label: 'XS', vcpu: 2, ramGb: 16 },
  { label: 'S', vcpu: 4, ramGb: 16 },
  { label: 'M', vcpu: 8, ramGb: 64 },
  { label: 'L', vcpu: 16, ramGb: 128 },
  { label: 'GPU (T4)', vcpu: 4, ramGb: 16, profile: 'gpu' },
  { label: 'XL', vcpu: 32, ramGb: 256 },
  { label: 'XXL', vcpu: 64, ramGb: 512 },
];

/**
 * A run's compute size. The editor now always emits a custom {vcpu, ramGb};
 * the `profile` variant is retained only for backward-compat deserialization.
 */
export type ComputeSpec =
  | { kind: 'profile'; profile: ResourceProfile }
  | { kind: 'custom'; vcpu: number; ramGb: number };

/** Coerce any spec into concrete vCPU/RAM (legacy profiles map to a size). */
export function specDims(spec: ComputeSpec): { vcpu: number; ramGb: number } {
  if (spec.kind === 'custom') return { vcpu: spec.vcpu, ramGb: spec.ramGb };
  const map: Record<ResourceProfile, { vcpu: number; ramGb: number }> = {
    micro: { vcpu: 1, ramGb: 4 },
    small: { vcpu: 2, ramGb: 16 },
    medium: { vcpu: 8, ramGb: 64 },
    large: { vcpu: 16, ramGb: 128 },
    gpu: { vcpu: 4, ramGb: 16 },
    xlarge: { vcpu: 32, ramGb: 256 },
    extreme: { vcpu: 64, ramGb: 512 },
  };
  return map[spec.profile] ?? { vcpu: 2, ramGb: 16 };
}

export function specCreditPerSecond(spec: ComputeSpec): number {
  // The GPU preset is priced by its accelerator, not by the CPU/RAM formula.
  if (spec.kind === 'profile' && spec.profile === 'gpu') {
    return GPU_PROFILE_CREDIT_PER_SECOND;
  }
  const { vcpu, ramGb } = specDims(spec);
  return customComputeRate(vcpu, ramGb);
}

export function specCreditsPerHour(spec: ComputeSpec): number {
  return Math.round(specCreditPerSecond(spec) * 3600);
}

export function specLabel(spec: ComputeSpec): string {
  if (spec.kind === 'profile' && spec.profile === 'gpu') {
    return '4 vCPU / 16 GB · T4 GPU';
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
 * accelerator cannot be expressed as CPU/RAM). Legacy CPU profile specs still
 * map to their custom dims for backward compatibility.
 */
export function specToRunBody(spec: ComputeSpec): {
  resourceProfile?: string;
  compute?: { vcpu: number; ramGb: number };
} {
  if (spec.kind === 'profile' && spec.profile === 'gpu') {
    return { resourceProfile: 'gpu' };
  }
  const { vcpu, ramGb } = specDims(spec);
  return { compute: { vcpu, ramGb } };
}
